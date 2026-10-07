"""Character-declared animation graph with explicit source and renderer paths.

Entries describe authored actions, not a reconstructed gameplay state machine.
Bank payloads are decoded only when requested. Disabled entries remain labeled.
"""
from pathlib import PurePosixPath
from .cu3 import FormatError
from .definitions import read_definition
from .animation_bank import AnimationBank
from .profiles import inspection_profile, profile_identity
from .resource_identity import logical_reference, logical_path, reference_cycles

MAX_ANIMATION_SETS = 1024


class AnimationGraphLimit(FormatError):
    pass


def _member_reference(file, suffix):
    reference = logical_reference(file)
    if reference.casefold().endswith('.an4'):
        return reference
    if suffix is None:
        raise FormatError('Automatic AN4 member naming is unverified for this inspection profile; supply a declared full AN4 name')
    return reference + '_DEF_' + suffix + '.AN4'


def _bank_member(bank, reference):
    entry = bank.entries.get(reference.casefold())
    if entry:
        return entry
    if '/' in reference:
        return None
    matches = [entry for entry in bank.entries.values()
               if PurePosixPath(entry['name']).name.casefold() == reference.casefold()]
    if len(matches) > 1:
        raise FormatError('Ambiguous animation bank basename: ' + reference + '; ' +
                          ', '.join(entry['name'] for entry in matches))
    return matches[0] if matches else None


def _loose_member(assets, member, set_reference, set_source):
    if '/' in member:
        return assets.find_exact(member, required=False)
    set_logical = logical_path(assets, set_source)
    set_parent = PurePosixPath(set_logical).parent if set_logical else None
    set_name = PurePosixPath(set_reference.replace('\\', '/')).stem.casefold()
    scoped = []
    for candidate in assets.files.get(member.casefold(), []):
        resource = candidate[1]['path'] if isinstance(candidate, tuple) else logical_path(assets, candidate)
        if not resource:
            continue
        path = PurePosixPath(resource)
        if ((set_parent is not None and str(set_parent) != '.' and
             path.parent.as_posix().casefold() == set_parent.as_posix().casefold()) or
                set_name in [part.casefold().removesuffix('_as') for part in path.parts[:-1]]):
            scoped.append(resource)
    # Providers compare logical paths case-insensitively and retain spelling.
    # Let their exact-path gate check case aliases and duplicate archive copies;
    # different logical paths still cannot be selected by an unqualified name.
    scoped = sorted(set(scoped))
    if len({path.casefold() for path in scoped}) > 1:
        raise FormatError('Ambiguous animation set member: ' + member + '; ' + ', '.join(scoped))
    return assets.find_exact(scoped[0]) if scoped else assets.find(member, required=False)


def catalog(assets, definition, provenance=None):
    game = getattr(assets, 'profile', None)
    profile = inspection_profile(game)
    suffix = profile['animation_suffix']
    roots = [obj['fields'].get('CharAnimSet Name', '') for obj in definition['objects']
             if obj['class'] == 'Character Anim Set Reference']
    pending = list(roots)
    visited, entries, issues, sources, edges, aliases = set(), [], [], [], [], {}
    while pending:
        name = pending.pop(0)
        if not name:
            continue
        try:
            name = logical_reference(name)
            source = assets.find(name, extension='.AS')
            source_logical = logical_path(assets, source) or str(source)
            key = source_logical.casefold()
            aliases[name.casefold()] = source_logical
            if key in visited:
                continue
            if len(visited) >= MAX_ANIMATION_SETS:
                raise AnimationGraphLimit('Animation reference graph exceeds limit')
            visited.add(key)
            data = read_definition(source)
            if provenance:
                provenance.record(source, 'animation-set', digest=data['source_sha256'])
            sources.append(str(source))
            for obj in data['objects']:
                if obj['class'] == 'Character Anim Set Reference':
                    child = obj['fields'].get('CharAnimSet Name','')
                    if child:
                        edges.append({'owner':source_logical,'reference':child})
                        pending.append(child)
            set_base = name[:-3] if name.casefold().endswith('.as') else name
            bank_reference = set_base + '_AN4_' + suffix if suffix else None
            bank_path = None
            if bank_reference and '/' not in name and logical_path(assets, source):
                sibling = PurePosixPath(source_logical).with_name(PurePosixPath(bank_reference).name + '.PAK')
                bank_path = assets.find_exact(sibling.as_posix(), required=False)
            if bank_reference and bank_path is None:
                bank_path = assets.find(bank_reference, extension='.PAK', required=False)
            bank = AnimationBank(bank_path) if bank_path else None
            if bank and provenance:
                provenance.record(bank_path, 'animation-bank-index', data=bank.data, export=False)
            for obj in data['objects']:
                fields = obj['fields']
                if obj['class'] not in ('Character Anim Entry', 'Character Anim Entry Core'):
                    continue
                for index in range(1, 10):
                    file = fields.get(f'ANI4 Animation File {index}', fields.get(f'Animation File {index}',
                           fields.get(f'Animation {index} File Name', '')))
                    if not file:
                        continue
                    path, packed, status, resolved_logical = '', '', 'Missing source', None
                    try:
                        member = _member_reference(file, suffix)
                        native_member = _bank_member(bank, member) if bank else None
                        if native_member:
                            path, packed, status = str(bank_path), native_member['name'], 'Bank member'
                            resolved_logical = logical_path(assets, bank_path)
                        else:
                            loose = _loose_member(assets, member, name, source)
                            if loose:
                                path, status = str(loose), 'Loose AN4'
                                resolved_logical = logical_path(assets, loose)
                    except (ValueError, OSError) as error:
                        status = str(error)
                        issues.append(name + ' / ' + str(file) + ': ' + str(error))
                    entries.append(dict(name=fields.get('Action') or file, set=name, source=path, member=packed,
                        source_logical_path=resolved_logical, file_reference=file, set_source=str(source),
                        set_logical_path=source_logical, set_sha256=data.get('source_sha256'),
                        game=game, renderer=profile['renderer'], animation_suffix=suffix,
                        actor=fields.get(f'Animation {index} Actor', fields.get(f'Animation Character {index}', '')),
                        clip=fields.get(f'Animation {index} Range', fields.get(f'Animation Range {index}', '')),
                        active=bool(fields.get('Active', 1)), status=status,
                        fps=fields.get('Frame Rate (FPS)', 30), loop=bool(fields.get('Cycle', 0)),
                        start=fields.get('Entry Frame', 1), end=fields.get('Exit Frame', 0)))
        except AnimationGraphLimit:
            raise
        except (ValueError, OSError, KeyError) as error:
            issues.append(str(name) + ': ' + str(error))
    for edge in edges:
        edge['resolved_target'] = aliases.get(str(edge['reference']).replace('\\','/').casefold())
    cycles=reference_cycles([(edge['owner'],edge['resolved_target']) for edge in edges if edge['resolved_target']])
    issues.extend('Cyclic animation-set references: ' + ' -> '.join(cycle) for cycle in cycles)
    return dict(roots=roots, sets=len(visited), entries=entries, issues=issues, sources=sources,
                edges=edges, cycles=cycles, profile_identity=profile_identity(game,inspection=True))
