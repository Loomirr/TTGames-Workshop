"""Decoded LSW1 PC BSA layer samples, without assuming morph ownership.

The native two-clip evaluator selects tracks by signed HGP layer index. Missing
tracks/components contribute zero. Target binding is deliberately separate.
"""
import math
import struct

from animation_records import AnimationError


def sample_layers(first, time, layers, *, second=None, second_time=None, blend=0.):
    """Return None for skipped layers and scalar lists for selected layers.

These are decoded channel values, not Blender shape-key assignments. A selected
layer absent from both clips has an empty list. No weight clamping is applied.
"""
    if first is None and second is None:
        raise AnimationError('At least one BSA clip is required')
    for clip in (first, second):
        if clip is not None and (clip.family != 'BSA' or clip.tracks > 32767 or clip.components > 32767):
            raise AnimationError('Layer sampling requires the observed signed-count PC BSA layout')
    if not isinstance(blend, (int, float)) or not math.isfinite(blend) or not 0 <= blend <= 1:
        raise AnimationError('Clip blend must be finite and between zero and one')
    for clip, at in ((first, time), (second, second_time)):
        if clip is not None and (not isinstance(at, (int, float)) or not math.isfinite(at)):
            raise AnimationError('Each clip requires a finite native frame time')
    if not isinstance(layers, (list, tuple)) or not 0 < len(layers) <= 32767:
        raise AnimationError('Supply a bounded explicit layer list')
    if any(type(layer) is not int or not -32768 <= layer <= 32767 for layer in layers):
        raise AnimationError('Layer IDs must be signed 16-bit integers')
    f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]
    blend = f32(blend)
    inverse = f32(1. - blend)
    result = []
    for layer in layers:
        if layer < 0:
            result.append(None)
            continue
        count_a = first.components if first and layer < first.tracks else 0
        count_b = second.components if second and layer < second.tracks else 0
        values = []
        for component in range(max(count_a, count_b)):
            a = first.evaluate_channel(layer, component, time) if component < count_a else 0.
            b = second.evaluate_channel(layer, component, second_time) if component < count_b else 0.
            try:
                value = f32(a * inverse + b * blend)
            except (OverflowError, struct.error) as error:
                raise AnimationError('Blended BSA value exceeds float32') from error
            if not math.isfinite(value):
                raise AnimationError('Blended BSA value is not finite')
            values.append(value)
        result.append(values)
    return result
