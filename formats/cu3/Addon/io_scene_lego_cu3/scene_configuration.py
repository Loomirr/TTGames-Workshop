"""Read declared LB3/LMSH1 cutscene stage dependencies without building them.

The game's registry/config files, not similar filenames, select levels and
shared art. Unknown commands are retained as data. This module never executes
script commands, substitutes characters, or claims a dependency can render.
"""
from pathlib import PurePosixPath
import re
from .cu3 import FormatError


def relative_reference(value):
    value = value.replace('\\', '/')
    parts = PurePosixPath(value).parts
    if not parts or value.startswith('/') or ':' in value or '..' in parts:
        raise FormatError('Configuration reference must remain inside the game root')
    return '/'.join(parts)


def commands(text, source):
    if len(text) > 16 * 1024 * 1024:
        raise FormatError('Configuration exceeds the supported text limit')
    rows = []
    for number, original in enumerate(text.splitlines(), 1):
        quoted, end, i = False, len(original), 0
        while i < len(original):
            char = original[i]
            if char == '"':
                quoted = not quoted
            elif not quoted and (char == ';' or original[i:i+2] == '//'):
                end = i
                break
            i += 1
        line = original[:end].strip()
        if not line:
            continue
        if quoted:
            raise FormatError(f'Unterminated configuration quote at {source}:{number}')
        tokens = re.findall(r'"[^"\r\n]*"|[^\s"]+', line)
        values = [token[1:-1] if token.startswith('"') else token for token in tokens]
        rows.append(dict(command=values[0].casefold(), args=values[1:], source=source, line=number))
    return rows


def blocks(rows, kind, notes=None):
    active, result = None, []
    for row in rows:
        if row['command'] == kind + '_start':
            if active is not None:
                raise FormatError('Nested ' + kind + ' configuration block')
            active = dict(source=row['source'], line=row['line'], commands=[])
        elif row['command'] == kind + '_end':
            if active is None:
                if notes is not None:
                    notes.append(dict(source=row['source'], line=row['line'], issue='Unmatched ' + kind + ' end outside any block'))
                    continue
                raise FormatError('Unmatched ' + kind + ' configuration end')
            result.append(active)
            active = None
        elif active is not None:
            active['commands'].append(row)
    if active is not None:
        raise FormatError('Unterminated ' + kind + ' configuration block')
    return result


def _single(block, key, required=True):
    rows = [row for row in block['commands'] if row['command'] == key]
    if not rows and not required:
        return None
    if len(rows) != 1 or len(rows[0]['args']) != 1:
        raise FormatError('Expected one ' + key + ' declaration in configuration block')
    return rows[0]['args'][0]


def _registry(read_text, root, include_commands, unresolved):
    visited, active, ordered = set(), set(), []
    def visit(reference):
        reference = relative_reference(reference)
        key = reference.casefold()
        if key in active:
            raise FormatError('Cyclic configuration include: ' + reference)
        if key in visited:
            return
        if len(active) >= 32:
            raise FormatError('Configuration include depth exceeds 32 files')
        if len(visited) >= 2048:
            raise FormatError('Configuration include graph is too large')
        if not reference.casefold().endswith('.txt'):
            raise FormatError('Configuration include must name a text file')
        visited.add(key)
        active.add(key)
        try:
            rows = commands(read_text(reference), reference)
        except FileNotFoundError as error:
            if reference.casefold() == root.casefold():
                raise
            unresolved.append(dict(reference=reference, issue=str(error)))
            active.remove(key)
            return
        for row in rows:
            if row['command'] in include_commands:
                if not row['args']:
                    raise FormatError('Configuration include has no path')
                visit(row['args'][0])
            else:
                ordered.append(row)
        active.remove(key)
    visit(root)
    return ordered


def resolve_configuration(cut, read_text, profile):
    """Resolve registry declarations using a bounded game-relative text reader.

    ``read_text`` receives a relative file reference and must raise for missing
    or ambiguous files. Returned stage prefixes describe declared game assets;
    their existence, format, transforms and shader fidelity need later checks.
    """
    versions = {'LB3': 19, 'LMSH1': 18}
    if profile not in versions or cut.version != versions[profile]:
        raise FormatError('Cutscene configuration profile/version is not verified')
    unresolved, notes = [], []
    rows = _registry(read_text, 'CUT/CUTSCENES_MAIN.TXT', {'txt_file'}, unresolved)
    matches = [block for block in blocks(rows, 'cutscene', notes)
               if (_single(block, 'file', False) or '').casefold() == cut.name.casefold()]
    if len(matches) != 1:
        raise FormatError(f'Expected one declared cutscene named {cut.name}; found {len(matches)}')
    cut_block = matches[0]
    level = _single(cut_block, 'level')
    level_rows = _registry(read_text, 'LEVELS/LEVELS.TXT', {'txt_file'}, unresolved)
    levels = [block for block in blocks(level_rows, 'level', notes)
              if (_single(block, 'file', False) or '').casefold() == level.casefold()]
    if len(levels) != 1:
        raise FormatError(f'Expected one registered level named {level}; found {len(levels)}')
    level_block = levels[0]
    stages = []
    for role, directory_key, file_key in (('primary','dir','file'),
                                         ('common','common_dir','common_file'),
                                         ('common_art','commonart_dir','commonart_file')):
        directory = _single(level_block, directory_key, role == 'primary')
        filename = _single(level_block, file_key, role == 'primary')
        if (directory is None) != (filename is None):
            raise FormatError('Incomplete shared level directory/file declaration')
        if directory is not None:
            stages.append(dict(role=role, resource_prefix=relative_reference('LEVELS/' + directory + '/' + filename),
                               registry_source=level_block['source'], registry_line=level_block['line']))
    replacements, props, hidden = [], [], []
    for row in cut_block['commands']:
        key, args = row['command'], row['args']
        if key in ('findcommonobject', 'dont_draw_special'):
            if len(args) != 1:
                raise FormatError('Malformed cutscene resource declaration')
            (props if key == 'findcommonobject' else hidden).append(dict(name=args[0], source=row['source'], line=row['line']))
        elif key == 'replace_character':
            if len(args) != 3 or args[1].casefold() != 'with':
                raise FormatError('Malformed cutscene character replacement')
            replacements.append(dict(original=args[0], replacement=args[2], source=row['source'], line=row['line']))
    return dict(schema='tt.cutscene-configuration.v1', cutscene=cut.name, profile=profile,
                cutscene_source=cut_block['source'], cutscene_line=cut_block['line'],
                level=level, stages=stages, common_objects=props,
                hidden_specials=hidden, character_replacements=replacements,
                unresolved_includes=unresolved, syntax_notes=notes,
                cutscene_commands=cut_block['commands'], level_commands=level_block['commands'],
                applied=False, scope='Registry declarations only. Geometry, placement, lighting, object visibility and character replacement have not been applied.')


def configuration_report(cut, read_text, profile):
    """Return unresolved configuration inputs as data for an import report.

    The reader must resolve the exact relative path. Basename fallback is not
    appropriate for authoritative configuration records.
    """
    requested = []
    def tracked(reference):
        row = dict(reference=reference, status='requested')
        requested.append(row)
        try:
            text = read_text(reference)
            row['status'] = 'read'
            return text
        except (OSError, ValueError, KeyError) as error:
            row.update(status='unresolved', issue=str(error))
            raise
    try:
        result = resolve_configuration(cut, tracked, profile)
        result['status'] = 'partial_declarations' if result['unresolved_includes'] or result['syntax_notes'] else 'resolved_declarations'
    except (OSError, ValueError, KeyError) as error:
        result = dict(schema='tt.cutscene-configuration.v1', cutscene=cut.name,
                      profile=profile, status='unresolved', applied=False, issue=str(error))
    result['configuration_files'] = requested
    return result


def configuration_report_from_assets(cut, assets, profile):
    """Use an exact-path extracted/archive asset provider for text inputs."""
    def read_text(reference):
        path = assets.find_exact(reference, required=False)
        if path is None:
            raise FileNotFoundError('Missing exact configuration file: ' + reference)
        if path.stat().st_size > 16 * 1024 * 1024:
            raise FormatError('Configuration exceeds the supported text limit')
        return path.read_text(encoding='utf-8-sig')
    return configuration_report(cut, read_text, profile)


def compile_character_replacements(configuration):
    """Compile simple declared resource substitutions, never actor renames.

    Duplicate sources and chains/cycles are rejected because execution order
    is not verified. Only bare resource IDs are accepted. The returned keys
    are case-folded for exact resource matching; targets retain source case.
    """
    if configuration.get('status') == 'unresolved':
        raise FormatError('Cannot apply character replacements from unresolved configuration')
    declarations = configuration.get('character_replacements', [])
    if not isinstance(declarations, list) or len(declarations) > 4096:
        raise FormatError('Invalid character replacement declaration list')
    result = {}
    for row in declarations:
        if not isinstance(row, dict):
            raise FormatError('Invalid character replacement declaration')
        original, replacement = row.get('original'), row.get('replacement')
        if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,254}', value)
               for value in (original, replacement)):
            raise FormatError('Character replacements require bare resource IDs')
        key = original.casefold()
        if key in result:
            raise FormatError('Duplicate character replacement source: ' + original)
        result[key] = replacement
    if set(result).intersection(value.casefold() for value in result.values()):
        raise FormatError('Chained or cyclic character replacements have unverified ordering')
    return result
