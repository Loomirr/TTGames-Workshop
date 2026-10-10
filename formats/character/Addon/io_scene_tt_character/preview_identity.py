"""Scene-local ancestry for animation links through repeated viewing copies."""
import json


def source_names(obj):
    names = {obj.name}
    if obj.get('tt_preview_source'):
        names.add(obj['tt_preview_source'])
    stored = obj.get('tt_preview_ancestors', '[]')
    try:
        ancestors = json.loads(stored)
    except (TypeError, ValueError):
        ancestors = []
    if isinstance(ancestors, list):
        names.update(name for name in ancestors if isinstance(name, str))
    return names


def record_copy(source, destination):
    destination['tt_preview_source'] = source.get('tt_preview_source', source.name)
    destination['tt_preview_ancestors'] = json.dumps(sorted(source_names(source)))


def linked_child(rig, name):
    # Resolve only inside this character. Never rebind an original object or
    # an unrelated character because it has the same historical display name.
    children = list(rig.children_recursive)
    exact = [child for child in children if child.name == name]
    matches = exact or [child for child in children if name in source_names(child)]
    return matches[0] if len(matches) == 1 else None
