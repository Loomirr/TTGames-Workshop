"""Keep one current version per download, preserving old packages locally."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def identity(relative):
    path = Path(relative)
    match = re.fullmatch(r'(.+?)[_-](\d+)\.(\d+)\.(\d+)([^/]*)\.zip', path.name)
    if path.is_absolute() or '..' in path.parts or not match:
        raise ValueError('Unrecognized versioned package path: ' + relative)
    prefix, major, minor, patch, suffix = match.groups()
    return (path.parent.as_posix(), prefix, suffix), tuple(map(int, (major, minor, patch)))


def keep_latest(builds=None, archive=None, *, apply=False):
    builds = Path(builds or ROOT / 'builds').resolve()
    archive = Path(archive or ROOT / 'local/build-history').resolve()
    if archive == builds or archive.is_relative_to(builds):
        raise ValueError('Historical archive must be outside published builds')
    manifest_path = builds / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    packages = manifest['packages']
    newest, paths = {}, set()
    for record in packages:
        relative = record['path']
        family, version = identity(relative)
        path = (builds / relative).resolve()
        if not path.is_relative_to(builds) or relative in paths:
            raise ValueError('Escaping or duplicate package path')
        paths.add(relative)
        data = path.read_bytes()
        if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Package checksum differs: ' + relative)
        if family not in newest or version > newest[family][0]:
            newest[family] = version, relative
        elif version == newest[family][0]:
            raise ValueError('Duplicate version for one tool: ' + relative)
    actual = {p.relative_to(builds).as_posix() for p in builds.rglob('*.zip')}
    if actual != paths:
        raise ValueError('Manifest must inventory every published ZIP before pruning')
    retained = {item[1] for item in newest.values()}
    obsolete = [record for record in packages if record['path'] not in retained]
    # Validate every destination before moving any package. Never replace a
    # different historical build that happens to share the same filename.
    for record in obsolete:
        destination = (archive / record['path']).resolve()
        if not destination.is_relative_to(archive):
            raise ValueError('Historical archive link escapes selected directory')
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Different historical package exists: ' + record['path'])
    if apply:
        for record in obsolete:
            source = (builds / record['path']).resolve()
            destination = (archive / record['path']).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Historical copy failed verification')
            source.unlink()
        manifest['packages'] = sorted((p for p in packages if p['path'] in retained), key=lambda p: p['path'])
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return [p['path'] for p in obsolete]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Archive superseded packages and update manifest')
    args = parser.parse_args()
    for name in keep_latest(apply=args.apply):
        print(('Archived: ' if args.apply else 'Would archive: ') + name)
