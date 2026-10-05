"""Explicit optional local extractor invocation. No shell or tool downloads."""
import json
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class FortniteSource:
    source: Path
    root: Path
    paks: Path | None = None


def _config(settings):
    path = Path(settings).resolve()
    if not path.is_file():
        raise ValueError('Set private Fortnite extractor settings in addon preferences before browsing Paks')
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict):
        raise ValueError('Fortnite extractor settings must be a JSON object')
    return path, config


def _private_options(settings):
    path, config = _config(settings)
    # Retain only supported options, never copy embedded archive keys or
    # unrelated private data into the generated per-cache settings.
    result = {key: config[key] for key in ('engineVersion', 'chunkHost') if key in config}
    for key in ('mappings', 'keyFile', 'oodle'):
        value = config.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError('Private Fortnite settings require a ' + key + ' file path')
        item = Path(value)
        result[key] = str((item if item.is_absolute() else path.parent / item).resolve())
    return result


def _default_cache():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / 'TTGamesWorkshop/Cache'


def _separate_cache(paks, cache):
    installation = paks
    if paks.name.casefold() == 'paks' and paks.parent.name.casefold() == 'content' and paks.parent.parent.name.casefold() == 'fortnitegame':
        installation = paks.parents[2]
    if cache.is_relative_to(installation) or installation.is_relative_to(cache):
        raise ValueError('Choose an asset cache separate from the Fortnite installation')


def resolve_source(source, cache_root=None, settings=None):
    """Resolve installed archives or an existing library without writing files."""
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError('Select an existing Fortnite game, Paks or exported-library folder')
    if (source / 'Exports').is_dir() and (source / 'Models').is_dir():
        return FortniteSource(source, source)
    paks = next((candidate for candidate in (source / 'FortniteGame/Content/Paks',
                    source / 'Content/Paks', source) if candidate.is_dir() and
                    any(p.is_file() and p.suffix.lower() in {'.pak', '.utoc'} for p in candidate.iterdir())), None)
    if paks is None:
        raise ValueError('No Fortnite PAK/UTOC archives or Exports/Models library found in that folder')
    paks = paks.resolve()
    cache = Path(cache_root).resolve() if cache_root else _default_cache().resolve()
    _separate_cache(paks, cache)
    archives = [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(paks.iterdir())
                if p.is_file() and p.suffix.lower() in {'.pak', '.utoc', '.ucas', '.uondemandtoc'}]
    options = _private_options(settings) if settings else {}
    dependencies = [(key, value, Path(value).stat().st_size, Path(value).stat().st_mtime_ns)
                    for key, value in options.items() if key in {'mappings', 'keyFile', 'oodle'} and Path(value).is_file()]
    identity = json.dumps([str(paks), archives, options, dependencies], sort_keys=True).encode('utf-8')
    digest = hashlib.sha256(identity).hexdigest()[:20]
    root = (cache / 'fortnite' / digest).resolve()
    if not root.is_relative_to(cache):
        raise ValueError('Unsafe Fortnite cache path')
    return FortniteSource(source, root, paks)


def backend_settings(settings, root, paks=None):
    """Validate a legacy config, or prepare installed-mode cache settings."""
    settings, root = Path(settings).resolve(), Path(root).resolve()
    if paks is None:
        path, config = _config(settings)
        output = Path(config['output'])
        if not output.is_absolute():
            output = path.parent / output
        if output.resolve() != root:
            raise ValueError('Extractor settings output must match the selected LEGO Fortnite export library')
        return settings
    paks = Path(paks).resolve()
    _separate_cache(paks, root)
    config = _private_options(settings)
    config.update(paks=str(paks), output=str(root))
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'workshop-extractor-settings.json'
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return path


def run_backend(executable, settings, root, command, resource=None, *, paks=None):
    executable, settings, root = Path(executable).resolve(), Path(settings).resolve(), Path(root).resolve()
    if not executable.is_file() or not settings.is_file():
        raise ValueError('Set an existing LEGO Fortnite extractor executable and private settings JSON in addon preferences')
    args = [str(executable), command]
    if command == 'export':
        if not resource or not isinstance(resource, str):
            raise ValueError('Missing indexed LEGO figure source package')
    elif command != 'index':
        raise ValueError('Unknown extractor operation')
    settings = backend_settings(settings, root, paks)
    args.append(str(settings))
    if command == 'export':
        args.append(resource)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with (root / 'workshop-extractor.log').open('wb') as log:
            result = subprocess.run(args, stdout=log, stderr=log, shell=False, cwd=settings.parent,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=300)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Extractor timed out after five minutes; see workshop-extractor.log in the export library') from error
    if result.returncode:
        raise ValueError('LEGO Fortnite extractor failed; see workshop-extractor.log in the export library')
