"""Character-declared animation reference graph, including shared banks.

Entries describe authored actions, not a reconstructed gameplay state machine.
Bank payloads are decoded only when requested. Disabled entries remain labeled.
"""
from pathlib import Path, PurePosixPath
from .cu3 import FormatError
from .definitions import read_definition
from .animation_bank import AnimationBank


def catalog(assets, definition):
    roots = [o['fields'].get('CharAnimSet Name', '') for o in definition['objects']
             if o['class'] == 'Character Anim Set Reference']
    pending, visited, entries, issues, sources = list(roots), set(), [], [], []
    while pending:
        name = pending.pop(0)
        if not name or name.casefold() in visited:
            continue
        if len(visited) >= 1024:
            raise FormatError('Animation reference graph exceeds limit')
        visited.add(name.casefold())
        try:
            source = assets.find(name, extension='.AS')
            sources.append(str(source))
            data = read_definition(source)
            suffix = 'NXG' if getattr(assets, 'profile', 'LMSH1') in ('LMSH1', 'LB3', 'HOBBIT') else 'DX11'
            bank_path = assets.find(name + '_AN4_' + suffix, extension='.PAK', required=False)
            bank = AnimationBank(bank_path) if bank_path else None
            for obj in data['objects']:
                fields = obj['fields']
                if obj['class'] == 'Character Anim Set Reference':
                    pending.append(fields.get('CharAnimSet Name', ''))
                if obj['class'] not in ('Character Anim Entry', 'Character Anim Entry Core'):
                    continue
                for i in range(1, 10):
                    file = fields.get(f'ANI4 Animation File {i}', fields.get(f'Animation File {i}', fields.get(f'Animation {i} File Name', '')))
                    if not file:
                        continue
                    member = PurePosixPath(file.replace('\\', '/')).name
                    if not member.casefold().endswith('.an4'):
                        member += '_DEF_' + suffix + '.AN4'
                    path, packed, status = '', '', 'Missing source'
                    if bank and member.casefold() in bank.entries:
                        path, packed, status = str(bank_path), bank.entries[member.casefold()]['name'], 'Bank member'
                    else:
                        # A set's own loose member takes precedence over same-named
                        # files from other banks. Never silently choose an ambiguous file.
                        candidates = list(assets.files.get(member.casefold(), []))
                        scoped = []
                        for candidate in candidates:
                            resource = candidate[1]['path'] if isinstance(candidate, tuple) else candidate.relative_to(assets.root).as_posix()
                            if name.casefold() in [p.casefold().removesuffix('_as') for p in PurePosixPath(resource).parts[:-1]]:
                                scoped.append(resource)
                        try:
                            loose = assets.find_exact(scoped[0]) if len(scoped) == 1 else assets.find(member, required=False)
                        except (ValueError, OSError) as error:
                            loose, status = None, str(error)
                            issues.append(name + ' / ' + member + ': ' + str(error))
                        if loose:
                            path, status = str(loose), 'Loose AN4'
                    entries.append(dict(name=fields.get('Action') or file, set=name, source=path, member=packed,
                        actor=fields.get(f'Animation {i} Actor', fields.get(f'Animation Character {i}', '')),
                        clip=fields.get(f'Animation {i} Range', fields.get(f'Animation Range {i}', '')),
                        active=bool(fields.get('Active', 1)), status=status,
                        fps=fields.get('Frame Rate (FPS)', 30), loop=bool(fields.get('Cycle', 0)),
                        start=fields.get('Entry Frame', 1), end=fields.get('Exit Frame', 0)))
        except (ValueError, OSError, KeyError) as error:
            issues.append(name + ': ' + str(error))
    return dict(roots=roots, sets=len(visited), entries=entries, issues=issues, sources=sources)
