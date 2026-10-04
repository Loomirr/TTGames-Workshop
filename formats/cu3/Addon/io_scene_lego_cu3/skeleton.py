"""Read source skeletons from observed LMSH1 NXG and LB3 DX11 GHG files."""
from pathlib import Path
import json
import math
from .cu3 import Reader, FormatError


def read_skeleton(path, expected_nodes=None):
    path = Path(path)
    if path.suffix.lower() == '.json':
        rig = json.loads(path.read_text(encoding='utf-8'))
        joints = rig['joints']
    else:
        data = path.read_bytes()
        r = Reader(data)
        candidates = []
        cursor = 0
        while True:
            at = data.find(b'LOGH', cursor)
            if at < 0:
                break
            cursor = at + 4
            ver = r.get('I', at + 4)
            try:
                joints, pos = [], at + 8
                if ver == 16:
                    if data[pos:pos + 4] != b'ROTV':
                        raise FormatError('GHG v16 joint array marker missing')
                    count = r.get('I', pos + 4)
                    pos += 8
                    for i in range(count):
                        length = r.get('H', pos)
                        pos += 2
                        name = r.string(pos, pos + length)
                        pos += length
                        orient, locator = list(r.get('16f', pos)), list(r.get('3f', pos + 64))
                        parent, flags = r.get('2B', pos + 76)
                        pos += 78
                        joints.append(dict(index=i, name=name, parent=None if parent == 255 else parent,
                                           flags=flags, orient_row_major=orient, locator_offset=locator))
                elif ver == 10:
                    nt = data.index(b'LBTN')
                    names_size = r.get('I', nt + 8)
                    names = nt + 12
                    count = r.get('I', pos)
                    pos += 4
                    for i in range(count):
                        no = r.get('I', pos)
                        name = r.string(names + no, names + names_size)
                        orient, locator = list(r.get('16f', pos + 4)), list(r.get('3f', pos + 68))
                        parent, flags = r.get('2B', pos + 80)
                        pos += 82
                        joints.append(dict(index=i, name=name, parent=None if parent == 255 else parent,
                                           flags=flags, orient_row_major=orient, locator_offset=locator))
                else:
                    continue
                if not 0 < count <= 255:
                    raise FormatError('Unsupported GHG joint count')
                for field in ('local_bind_row_major', 'inverse_world_bind_row_major'):
                    if ver == 16:
                        if data[pos:pos + 4] != b'ROTV':
                            raise FormatError('GHG matrix array marker missing')
                        pos += 4
                    if r.get('I', pos) != count:
                        raise FormatError('GHG bind matrix count differs from joints')
                    pos += 4
                    for j in joints:
                        j[field] = list(r.get('16f', pos))
                        pos += 64
                bind_end = pos
                def array_count():
                    nonlocal pos
                    if ver == 16:
                        if data[pos:pos + 4] != b'ROTV':
                            raise FormatError('Missing HGOL array marker')
                        pos += 4
                    n = r.get('I', pos)
                    pos += 4
                    if n > 65536:
                        raise FormatError('Unreasonable HGOL array count')
                    return n
                n = array_count()
                pre_poi_bytes = list(data[pos:pos+n])
                pos += n
                pois = []
                for k in range(array_count()):
                    if ver == 16:
                        length = r.get('H', pos)
                        pos += 2
                        label = r.string(pos, pos + length)
                        pos += length
                    else:
                        no = r.get('I', pos)
                        pos += 4
                        label = r.string(names + no, names + names_size)
                    pois.append(dict(name=label, matrix=list(r.get('16f', pos)), joint=r.get('B', pos + 64)))
                    pos += 65
                n = array_count()
                post_poi_bytes = list(data[pos:pos+n])
                pos += n
                length = r.get('I', pos)
                pos += 4 + length
                metadata = []
                for k in range(array_count()):
                    kind, joint, special, layer = r.get('BBHB', pos)
                    metadata.append(dict(kind=kind, joint=joint, special=special, layer=layer))
                    pos += 5
                layers = []
                for k in range(array_count()):
                    if ver == 16:
                        length = r.get('H', pos)
                        pos += 2
                        label = r.string(pos, pos + length)
                        pos += length
                    else:
                        no = r.get('I', pos)
                        pos += 4
                        label = r.string(names + no, names + names_size)
                    mi, rigids, skins = r.get('3H', pos)
                    pos += 6
                    layers.append(dict(name=label, metadata_index=mi, rigids=rigids, skins=skins))
                candidates.append(dict(source=str(path.resolve()), hgol_offset=at, version=ver, joints=joints,
                                       bind_end_offset=bind_end, points_of_interest=pois,
                                       pre_poi_bytes=pre_poi_bytes,post_poi_bytes=post_poi_bytes,
                                       layer_metadata=metadata, layers=layers))
            except (ValueError, UnicodeError) as error:
                continue
        compatible = [c for c in candidates if expected_nodes is None or len(c['joints']) == expected_nodes]
        if not compatible:
            raise FormatError('No supported matching GHG skeleton (observed HGOL versions 10 and 16 only)')
        rig = compatible[0]
        joints = rig['joints']
    if expected_nodes is not None and len(joints) != expected_nodes:
        raise FormatError(f'Skeleton has {len(joints)} joints; animation has {expected_nodes}')
    for i, j in enumerate(joints):
        if j['index'] != i or (j['parent'] is not None and not 0 <= j['parent'] < i):
            raise FormatError('Skeleton indices/parents are incompatible')
        if not all(math.isfinite(x) for key in ('local_bind_row_major', 'inverse_world_bind_row_major') for x in j[key]):
            raise FormatError('Non-finite skeleton bind matrix')
    if len({j['name'] for j in joints}) != len(joints):
        raise FormatError('Duplicate skeleton bone names')
    return rig
