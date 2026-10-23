"""Observed serialized ANI-D detail selector; offsets stay block-relative."""
from .cu3 import Animation, FormatError


def detail_tracks(animation):
    """Return every native detail slot, including zero-offset base aliases."""
    a = animation
    if not a.offsets[6]:
        return [a]
    if a.variant not in ('ANIB','ANID') or a.endian not in ('>','<') or a.reader.get('B', a.at + 18) & 1:
        raise FormatError('Unverified or already-relocated animation detail table')
    r = a.reader
    at = a.at + a.offsets[6]
    if a.offsets[6] < 80 or at + 8 > a.limit:
        raise FormatError('Animation detail header outside its source')
    count, reserved, pointer = r.get('2HI', at, a.endian)
    if not 1 <= count <= 16 or reserved or pointer < 80 or a.at + pointer + count * 4 > a.limit:
        raise FormatError('Unverified animation detail count or pointer')
    offsets = r.get(f'{count}I', a.at + pointer, a.endian)
    if count == 1:offsets = (offsets,)
    if offsets[0]:
        raise FormatError('Animation detail slot zero must retain the base track')
    tracks, seen = [], {0: a}
    for offset in offsets:
        if offset not in seen:
            if offset < 80 or a.at + offset + 80 > a.limit:
                raise FormatError('Animation detail track outside its source')
            child = Animation(r, a.at + offset, a.limit)
            if child.variant != a.variant or child.endian != a.endian or any(child.offsets[5:]):
                raise FormatError('Nested or unknown animation detail auxiliaries')
            if child.frames != a.frames or child.curves != a.curves:
                raise FormatError('Animation detail timing/channels disagree with base')
            child.prepare(scene_channels=True)
            seen[offset] = child
        tracks.append(seen[offset])
    return tracks


def model_detail_skeletons(skeleton):
    """Revalidate the retained model's complete native variant ownership."""
    import hashlib
    from pathlib import Path
    from .native_model import load_model
    from .skeleton import scan_skeleton_candidates, select_skeleton
    path = Path(skeleton['source'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != skeleton['source_sha256']:
        raise FormatError('Native skeleton source changed since import')
    model = load_model(path, skeleton_identity=skeleton['identity'])
    candidates = scan_skeleton_candidates(path)['candidates']
    base = select_skeleton(candidates, display=model['display'], mesh=model)
    if base['identity'] != skeleton['identity'] or not base.get('native_variant_group'):
        raise FormatError('Animation detail export requires the verified native base rig')
    candidates.sort(key=lambda item: item['native_variant_index'])
    if [item['native_variant_index'] for item in candidates] != list(range(len(candidates))):
        raise FormatError('Native skeleton detail slots are not contiguous')
    return candidates
