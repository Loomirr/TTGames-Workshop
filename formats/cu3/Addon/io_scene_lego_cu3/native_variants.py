"""Counted HGOL 10/12/16/17 model variants observed in original NXG/DX11 bodies.

The zero-threshold resource has an identity joint map and no remap to another
resource. Other records explicitly map its metadata to their own metadata.
This is a native relationship, not a preference for the first scanned marker.
Other trailer versions/layouts remain unverified.
"""
import hashlib
import math
from .cu3 import Reader, FormatError


def annotate_variant_group(data, candidates, errors):
    """Attach a complete counted group, or retain a refusal for its candidates."""
    starts = [c['hgol_offset'] for c in candidates
              if c['hgol_offset'] >= 20 and
              data[c['hgol_offset']-20:c['hgol_offset']-4] == b'5LVI\0\0\0\1\0\0\0\0ROTV']
    if not starts:
        return
    if (len(starts) == len(candidates) == 1 and
            Reader(data).get('I', starts[0]-4) == 1):
        # Already-unique skeletons retain their established version/layout
        # gates. This new decoder resolves counted multi-resource ambiguity.
        return
    try:
        if len(starts) != 1 or errors:
            raise FormatError('Native variant group has extra or undecodable HGOL/name-table interpretations')
        ordered = sorted(candidates, key=lambda c: c['hgol_offset'])
        start = starts[0]
        reader = Reader(data)
        count = reader.get('I', start-4)
        if not 1 <= count <= 64 or count != len(ordered) or ordered[0]['hgol_offset'] != start:
            raise FormatError('Native variant count does not cover every HGOL interpretation')
        version = ordered[0]['version']
        if version not in (10, 12, 16, 17) or any(c['version'] != version for c in ordered):
            raise FormatError('Native variant trailer requires observed HGOL 10, 12, 16 or 17 throughout')
        if len({c.get('name_table_offset') for c in ordered}) != 1:
            raise FormatError('Native variants disagree on name-table ownership')
        decoded = []
        for index, candidate in enumerate(ordered):
            tail = _trailer(data, reader, candidate)
            if index+1 < count and tail['end_offset'] != ordered[index+1]['hgol_offset']:
                raise FormatError('Native variant trailer does not end at the next counted HGOL')
            decoded.append(tail)
        end = decoded[-1]['end_offset']
        fence = b'\0\0\0\0\1ATEM' if version in (10,12) else b'\0\0\0\0ATEM'
        if data[end:end+len(fence)] != fence:
            raise FormatError('Native variant group has an unverified terminal boundary')
        group = dict(schema='tt.native-hgol-variants.v1', array_offset=start-8,
                     count=count, version=version, end_offset=end,
                     candidate_offsets=[c['hgol_offset'] for c in ordered],
                     serialized_sha256=hashlib.sha256(data[start-20:end+len(fence)]).hexdigest())
        for index, (candidate, tail) in enumerate(zip(ordered, decoded)):
            candidate['native_variant'] = tail
            candidate['native_variant_group'] = group
            candidate['native_variant_index'] = index
    except (ValueError, KeyError, TypeError) as error:
        for candidate in candidates:
            candidate['native_variant_error'] = str(error)


def _trailer(data, reader, candidate):
    pos = candidate['end_offset']
    start = pos
    typed = candidate['version'] in (12,16,17)
    secondary_map = candidate['version'] in (10,12)
    def get(fmt, size):
        nonlocal pos
        value = reader.get(fmt, pos)
        pos += size
        return value
    def array(fmt, width, maximum):
        nonlocal pos
        if typed:
            if data[pos:pos+4] != b'ROTV':
                raise FormatError('Native variant array marker missing')
            pos += 4
        count = get('I', 4)
        if count > maximum:
            raise FormatError('Native variant array exceeds its verified bound')
        return [get(fmt, width) for _ in range(count)]
    if array('B', 1, 0):
        raise FormatError('Unverified native variant auxiliary array')
    prefix = list(get('2I', 8))
    bounds = list(get('6f', 24))
    vector = list(get('3f', 12))
    threshold_offset = pos
    threshold = get('f', 4)
    if prefix != [0, 0] or vector != [0, 0, 0]:
        raise FormatError('Unverified native variant auxiliary fields')
    if not all(math.isfinite(v) for v in bounds+[threshold]) or threshold < 0:
        raise FormatError('Invalid native variant bounds or threshold')
    if any(bounds[i] > bounds[i+3] for i in range(3)):
        raise FormatError('Reversed native variant bounds')
    joint_map = array('B', 1, 255)
    if len(joint_map) != len(candidate['joints']):
        raise FormatError('Native variant joint-map size differs from its rig')
    secondary = array('B', 1, 255) if secondary_map else None
    scale = get('f', 4) if secondary_map else None
    if secondary_map and (secondary != joint_map or scale != 1):
        raise FormatError('Unverified HGOL 10/12 secondary joint map or scale')
    metadata_map = array('H', 2, 65536)
    if get('B', 1) != 0:
        raise FormatError('Unverified native variant terminal flag')
    # Avengers HGOL 17 retains four opaque bytes and a second zero flag
    # between the remap and the next counted resource (or terminal fence).
    # Preserve the bytes without treating them as a pointer or checksum.
    extension = get('4s', 4).hex() if candidate['version'] == 17 else None
    if candidate['version'] == 17 and get('B', 1) != 0:
        raise FormatError('Unverified HGOL 17 extension flag')
    return dict(offset=start, end_offset=pos, threshold_offset=threshold_offset,
                threshold=threshold, bounds=bounds, joint_map=joint_map,
                secondary_joint_map=secondary, scale=scale, metadata_map=metadata_map, extension_hex=extension,
                serialized_sha256=hashlib.sha256(data[start:pos]).hexdigest())


def select_variant_base(candidates, *, display, mesh):
    """Validate the whole native association before returning its unique base."""
    if display is None or mesh is None:
        raise FormatError('Native multi-rig ownership requires decoded mesh and display associations')
    groups = [c.get('native_variant_group') for c in candidates]
    if not groups or groups[0] is None or any(g != groups[0] for g in groups):
        raise FormatError('HGOL candidates do not belong to one complete native variant group')
    group = groups[0]
    if sorted(c['hgol_offset'] for c in candidates) != group['candidate_offsets']:
        raise FormatError('Native variant selection cannot discard another candidate')
    bases = [c for c in candidates if c['native_variant']['threshold'] == 0
             and c['native_variant']['metadata_map'] == []
             and c['native_variant']['joint_map'] == list(range(len(c['joints'])))]
    if len(bases) != 1:
        raise FormatError('Native variant group does not identify one zero-threshold identity base')
    base = bases[0]
    base_layers = [layer['name'] for layer in base['layers']]
    all_specials = set()
    all_parts = set()
    cross_layers = []
    omissions = []
    from .native_display import model_bindings
    for candidate in candidates:
        tail = candidate['native_variant']
        joint_map = tail['joint_map']
        if (len(joint_map) != len(set(joint_map)) or
                any(index >= len(base['joints']) for index in joint_map)):
            raise FormatError('Native variant joint map is duplicated or outside the base rig')
        reverse = {old:new for new,old in enumerate(joint_map)}
        for index, original in enumerate(joint_map):
            joint = candidate['joints'][index]
            source = base['joints'][original]
            parent = source['parent']
            while parent is not None and parent not in reverse:
                parent = base['joints'][parent]['parent']
            if joint['name'] != source['name'] or joint['parent'] != (reverse[parent] if parent is not None else None):
                raise FormatError('Native variant joint map disagrees with names or retained hierarchy')
        if [layer['name'] for layer in candidate['layers']] != base_layers:
            raise FormatError('Native variants disagree on numbered layer identities')
        metadata = candidate['layer_metadata']
        owned = set()
        covered = []
        for index, layer in enumerate(candidate['layers']):
            first = layer['metadata_index']
            last = first+layer['rigids']+layer['skins']
            if first < 0 or last > len(metadata):
                raise FormatError('Native variant layer exceeds its metadata table')
            covered.extend(range(first,last))
            if (sum(row['kind'] == 0 for row in metadata[first:last]) != layer['rigids'] or
                    sum(row['kind'] in (1,3) for row in metadata[first:last]) != layer['skins']):
                raise FormatError('Native variant layer rigid/skin counts disagree with its metadata')
            for row in metadata[first:last]:
                if row['layer'] != index or row['kind'] not in (0,1,3):
                    raise FormatError('Native variant metadata has an unverified layer or kind')
                special_index = row['special']
                if not 0 <= special_index < len(display['specials']) or special_index in owned:
                    raise FormatError('Native variant display ownership is duplicated or outside its table')
                owned.add(special_index)
                special = display['specials'][special_index]
                if special.get('unsupported_commands'):
                    raise FormatError('Native variant contains unsupported display commands')
                rigid = row['joint'] if row['kind'] == 0 else None
                if rigid is not None and not 0 <= rigid < len(candidate['joints']):
                    raise FormatError('Native variant rigid joint is outside its rig')
                for binding in model_bindings(display,special):
                    part = binding['part']
                    if not 0 <= part < len(mesh['parts']):
                        raise FormatError('Native variant draw references an absent mesh part')
                    all_parts.add(part)
                    if rigid is None:
                        for vertex in mesh['parts'][part]['vertices']:
                            weights = vertex.get('weights',())
                            if (not weights or not any(weight > 0 for _,weight in weights) or
                                    any(not 0 <= joint < len(candidate['joints']) or not math.isfinite(weight)
                                        or weight < 0 for joint,weight in weights)):
                                raise FormatError('Native variant skin palette is incompatible with its own rig')
        if sorted(covered) != list(range(len(metadata))) or owned & all_specials:
            raise FormatError('Native variant metadata/display ownership is incomplete or overlaps')
        all_specials.update(owned)
        mapping = tail['metadata_map']
        if candidate is base:
            continue
        if tail['threshold'] <= 0 or len(mapping) != len(base['layer_metadata']):
            raise FormatError('Native variant remap does not reference the full base metadata table')
        used = set()
        for index, target in enumerate(mapping):
            if target == 65535:
                continue
            if target >= len(metadata) or target in used:
                raise FormatError('Native variant metadata remap is duplicated or outside its table')
            used.add(target)
            source, row = base['layer_metadata'][index], metadata[target]
            # The explicit remap identifies the corresponding draw. Native
            # cape LODs rename it; face LODs replace morph skins with rigids.
            # Each endpoint's ownership/palette was validated above, so neither
            # matching labels nor matching representation kinds are required.
            if (source['kind'] == row['kind'] == 0 and
                    source['joint'] != joint_map[row['joint']]):
                raise FormatError('Native variant remap disagrees with its rigid binding')
            # Original DX11 explicitly relocates one repeated StudHi draw to
            # another valid layer. Preserve that map; never force layer equality.
            if source['layer'] != row['layer']:
                cross_layers.append(dict(candidate_offset=candidate['hgol_offset'],base_metadata=index,
                                         variant_metadata=target,base_layer=source['layer'],variant_layer=row['layer']))
        omissions.append(dict(candidate_offset=candidate['hgol_offset'],
                              omitted_base_entries=mapping.count(65535),
                              unmapped_variant_entries=sorted(set(range(len(metadata)))-used)))
    if all_specials != set(range(len(display['specials']))) or all_parts != set(range(len(mesh['parts']))):
        raise FormatError('Native variant group does not cover the complete model display/geometry')
    evidence = dict(group,base_offset=base['hgol_offset'],
                    reason='verified_native_variant_base',mesh_associations_checked=True,
                    cross_layer_remaps=cross_layers,remap_omissions=omissions)
    return base, evidence
