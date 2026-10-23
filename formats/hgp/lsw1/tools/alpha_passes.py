"""Decoded PC alpha helper states and a restricted ordered-fragment reference.

The reference consumes caller-supplied draw order, quantized alpha and depth.
It does not infer native sorting, rasterization, alpha quantization or GPU state.
"""
import math


def helper_states(attributes, secondary):
    """State calls from original helpers 0x521610 / 0x521720, in order."""
    if type(attributes) is not int or not 0 <= attributes <= 0xffffffff:
        raise ValueError('Attributes must be a native uint32')
    if type(secondary) is not int or not 0 <= secondary <= 0xffffffff:
        raise ValueError('Secondary attributes must be a native uint32')
    mode = (attributes >> 20) & 7
    if mode == 1:
        return [(15, 0)], []
    first = [(15, 1), (25, (1, 8, 2, 4, 3, 7, 5, 6)[mode]),
             (24, ((attributes >> 23) & 255) * 2)]
    second = [(25, (8, 1, 7, 5, 6, 2, 4, 3)[mode])]
    second += ([(168, 0), (14, 0)], [(14, 0)], [(168, 0), (14, 1)],
               [(168, 7), (14, 0)])[secondary & 3]
    return first, second


def alpha_test(function, alpha, reference):
    if type(alpha) is not int or not 0 <= alpha <= 255 or type(reference) is not int or not 0 <= reference <= 255:
        raise ValueError('Supply explicit 8-bit alpha and reference; out-of-range device behavior is unverified')
    if type(function) is not int or not 1 <= function <= 8:
        raise ValueError('Unknown native comparison')
    return (False, alpha < reference, alpha == reference, alpha <= reference,
            alpha > reference, alpha != reference, alpha >= reference, True)[function - 1]


def fragment(color, depth, *, source, source_depth, alpha_byte, attributes, secondary):
    """One explicitly eligible ordinary source-alpha draw, both queued passes.

    Assumptions supplied by this experiment: initial RGBA write mask 15, depth
    writes enabled, less-or-equal depth test, source-alpha blending of all four
    channels. Source alpha is an explicit normalized shader output; alpha_byte
    is the separately supplied alpha-test input. Native quantization is not guessed.
    """
    first, second = helper_states(attributes, secondary)
    if attributes & 15 != 1 or ((attributes >> 20) & 7) == 1:
        raise ValueError('Reference supports only explicitly eligible two-pass source-alpha draws')
    if any(len(v) != 4 or any(not math.isfinite(c) or not 0 <= c <= 1 for c in v)
           for v in (color, source)) or any(not math.isfinite(z) or not 0 <= z <= 1 for z in (depth, source_depth)):
        raise ValueError('Supply normalized finite RGBA and depth')
    state = {168: 15, 14: 1}
    output = list(color); trace = []
    for calls in (first, second):
        state.update(calls)
        passes = alpha_test(state[25], alpha_byte, state[24]) and source_depth <= depth
        if passes:
            for channel in range(4):
                if state[168] & (1 << channel):
                    output[channel] = source[channel] * source[3] + output[channel] * (1 - source[3])
            if state[14]:
                depth = source_depth
        trace.append(dict(passed=passes, color_mask=state[168], depth_write=bool(state[14])))
    return tuple(output), depth, trace
