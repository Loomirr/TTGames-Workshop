"""Logical resource identities retained separately from labels and file digests."""
from pathlib import Path, PurePosixPath
import re
from .cu3 import FormatError


def logical_reference(reference):
    name = str(reference).replace('\\', '/')
    if (not name or len(name) > 4096 or name.startswith('/') or ':' in name or
            any(part in ('', '.', '..') for part in name.split('/')) or
            any(ord(char) < 32 for char in name)):
        raise FormatError('Asset reference must be relative to the selected game root')
    return name


def logical_path(assets, path):
    """Return provider-relative spelling without collapsing different resources."""
    path = Path(path)
    try:
        return path.relative_to(Path(assets.root)).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(Path(assets.root).resolve()).as_posix()
        except ValueError:
            return None


def resource_key(reference):
    """Compare exact logical resources, retaining directories in the key."""
    clean = logical_reference(reference)
    suffix = PurePosixPath(clean).suffix
    if suffix.casefold() in ('.cd', '.ghg', '.gsc'):
        clean = clean[:-len(suffix)]
    for renderer in ('_NXG', '_DX11'):
        if clean.casefold().endswith(renderer.casefold()):
            clean = clean[:-len(renderer)]
            break
    return clean.casefold()


def model_resource_identity(source, skeleton, *, assets=None, definition=None, reference='', game=None):
    names = []
    values = [reference]
    if definition:
        values.extend(definition['character'].get(field, '') for field in ('Skeleton Name', 'Override Model File'))
    for value in values:
        if value and str(value) not in names:
            logical_reference(value)
            names.append(str(value))
    logical = logical_path(assets, source) if assets else None
    if logical and logical not in names:
        names.append(logical)
    binding = skeleton.get('identity') if skeleton else None
    return {
        'schema': 'tt.resource-identity.v1', 'game': game, 'logical_path': logical,
        'declared_resources': names,
        'native_root_name': skeleton['joints'][0]['name'] if skeleton and skeleton.get('joints') else None,
        'skeleton_identity': binding,
        'definition_source': definition.get('source') if definition else None,
        'definition_sha256': definition.get('source_sha256') if definition else None,
    }


def actor_identity_evidence(actor, identity):
    """Match recovered names; no unknown numeric resource IDs are interpreted.

    Standalone AN4 contains no bind matrices. A named match is usable only
    under a matched parent, with unique claims and compatible record bounds;
    callers enforce those additional requirements.
    """
    if not identity or identity.get('schema') != 'tt.resource-identity.v1':
        return None
    name = actor.get('name', '')
    # Instance prefixes are an observed root-resource convention, not clip names.
    resource = re.sub(r'^instance[^_]*_', '', name, flags=re.I)
    try:
        key = resource_key(resource)
    except FormatError:
        return None
    declared = [ref for ref in identity.get('declared_resources', []) if resource_key(ref) == key]
    if declared:
        return {'kind': 'declared_resource', 'actor_name': name, 'declared_resource': declared[0]}
    root = identity.get('native_root_name')
    if root and name.casefold() == root.casefold() and identity.get('skeleton_identity'):
        return {'kind': 'native_skeleton_root', 'actor_name': name, 'native_root_name': root,
                'binding_sha256': identity['skeleton_identity'].get('binding_sha256')}
    return None


def reference_cycles(edges, identities=None):
    """Report directed backedges after discovery, including shared-root cycles.

    Iterative traversal avoids recursion limits and never enumerates all paths.
    Optional resolved identities merge aliases of the same owned resource while
    reports retain the first declared spelling.
    """
    identities = identities or {}
    graph, labels = {}, {}

    def key(name):
        normalized = str(name).replace('\\','/').casefold()
        canonical = identities.get(normalized,normalized)
        labels.setdefault(canonical,str(name))
        graph.setdefault(canonical,[])
        return canonical

    for owner, resource in edges:
        source, target = key(owner), key(resource)
        if target not in graph[source]:
            graph[source].append(target)
    colors, cycles = {}, []
    for start in graph:
        if colors.get(start):
            continue
        colors[start] = 1
        path, positions = [start], {start:0}
        stack = [(start,iter(graph[start]))]
        while stack:
            node, children = stack[-1]
            try:
                child = next(children)
            except StopIteration:
                stack.pop();path.pop();positions.pop(node)
                colors[node] = 2
                continue
            if colors.get(child) == 1:
                cycles.append([labels[item] for item in path[positions[child]:]] + [labels[child]])
            elif not colors.get(child):
                colors[child] = 1
                positions[child] = len(path)
                path.append(child)
                stack.append((child,iter(graph[child])))
    return cycles
