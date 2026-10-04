"""Observed v18/v19 camera footer and AN4 visibility tracks.

Typed camera association uses serialized footer references, not channel-count
guesses. Remaining footer systems are retained for further reconstruction.
"""
from .cu3 import FormatError

def read_rigids(cut, cinematic):
    r = cut.reader
    at = cinematic['remaining_offset'] + 35
    count = r.get('I', at)
    at += 4
    if count > 10000:
        raise FormatError('Unreasonable rigid actor count')
    by_offset = {a.at - cut.blob_start: a for a in cut.standalone}
    records = []
    for i in range(count):
        name, matrix, offset, flags = r.get('3IH', at)
        if matrix >= len(cut.matrices) or offset not in by_offset:
            raise FormatError('Invalid rigid transform reference')
        anim = by_offset[offset]
        error = None
        try:
            anim.prepare(scene_channels=True)
        except FormatError as exc:
            error = str(exc)
        records.append(dict(name=r.string(cut.strings_start + name, cut.strings_end),
                            index=i, record_offset=at,
                            matrix_index=matrix, animation=anim, flags=flags,
                            extra=r.get('3H', at + 14), unsupported=error))
        at += 20
    return records

def read_cameras(cut):
    if cut.version == 30:
        raise FormatError('DCSV camera/object footer is not yet verified')
    r = cut.reader
    at = cut.footer_start
    count = r.get('I', at)
    if count > 65536:
        raise FormatError('Invalid scene vector table')
    at += 4 + count * 12
    exposure, aspect = r.get('2f', at)
    cameras = r.get('H', at + 12)
    if cameras > 256 or not 0.1 < aspect < 10:
        raise FormatError('Unsupported camera footer')
    at += 16
    by_offset = {a.at - cut.blob_start: a for a in cut.standalone}
    records = []
    for i in range(cameras):
        matrix, offset, flags = r.get('HIH', at)
        if matrix >= len(cut.matrices) or offset and offset not in by_offset:
            raise FormatError('Invalid typed camera reference')
        film_height, film_width = r.get('2f', at + 8)
        lens = r.get('f', at + 26)
        if not 0 < lens < 10000 or not 0 < film_width < 10:
            raise FormatError('Invalid camera optics')
        anim = by_offset.get(offset)
        if anim:
            anim.prepare(scene_channels=True)
        records.append(dict(index=i, matrix_index=matrix, animation=anim,
                            flags=flags, film_height_inches=film_height,
                            film_width_inches=film_width, lens_mm=lens,
                            focus_matrix=r.get('H', at + 16)))
        at += 64 if cut.version >= 19 else 56
    unknown = r.get('H', at)
    at += 2
    states = []
    for i in range(3):
        state = read_state(r, at)
        states.append(state)
        at = state['end_offset']
    if any(v >= cameras for v in states[0]['values']):
        raise FormatError('Shot selection references an absent camera')
    return dict(cameras=records, shots=states[0], focus_states=states[1:],
                aspect=aspect, exposure=exposure, unknown=unknown,
                remaining_offset=at)

def read_state(r, at):
    flags, first, last = r.get('3H', at)
    count = r.get('I', at + 6)
    if not 0 < count < 100000:
        raise FormatError('Invalid state key count')
    times = r.get(f'{count}f', at + 10)
    times = [times] if count == 1 else list(times)
    values_count = r.get('I', at + 10 + count * 4)
    if values_count != count or times != sorted(times):
        raise FormatError('State key arrays disagree')
    start = at + 14 + count * 4
    values = [r.get('B', start + i) for i in range(count)]
    return dict(flags=flags, first=first, last=last, times=times,
                values=values, end_offset=start + count)

def visibility(cut, actor):
    anim = actor.get('visibility_animation')
    if not anim:
        own = [True] * cut.frames
    else:
        anim.prepare(scene_channels=True)
        # Six transform channels have no visibility channel. Character scene
        # tracks use channel 6; channel 9 on 10-channel rigid tracks follows
        # their scale triplet. Never interpret rotation Z as visibility.
        control_channel = getattr(anim, 'control_visibility_channel', None)
        channel = control_channel if control_channel is not None else 6 if anim.curves == 7 else 9 if anim.curves == 10 else None
        values = [anim.sample(f)[0][channel] for f in range(cut.frames)] if channel is not None else None
        if values is not None and control_channel is not None and any(v not in (0,1) for v in values):
            raise FormatError('Non-boolean scene-control values are not verified as visibility. Disable source visibility to inspect the compatible skeletal pose separately.')
        own = [bool(round(value)) for value in values] if values is not None else [True] * cut.frames
    if actor['parent'] is not None:
        parent = visibility(cut, cut.actors[actor['parent']])
        own = [a and b for a, b in zip(own, parent)]
    return own
