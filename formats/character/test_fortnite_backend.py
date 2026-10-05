"""Constructed archive/settings boundary checks; no game data or Blender."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fortnite_backend', Path(__file__).parent / 'Addon/io_scene_tt_character/fortnite_backend.py')
backend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend
spec.loader.exec_module(backend)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.game = self.root / 'Game'
        self.paks = self.game / 'FortniteGame/Content/Paks'
        self.paks.mkdir(parents=True)
        (self.paks / 'chunk.utoc').write_bytes(b'archive fixture')
        self.cache = self.root / 'Cache'
        self.private = self.root / 'Private'
        self.private.mkdir()
        for name in ('map.usmap', 'keys.json', 'oodle.dll'):
            (self.private / name).write_bytes(b'private fixture')
        self.settings = self.private / 'settings.json'
        self.settings.write_text(json.dumps(dict(paks='old-source', output='old-output', mappings='map.usmap',
            keyFile='keys.json', oodle='oodle.dll', engineVersion='GAME_UE6_0',
            extra_private_data='not copied', keys={'secret': 'not copied'})))

    def tearDown(self):
        self.temp.cleanup()

    def resolve(self, source=None, cache=None):
        return backend.resolve_source(source or self.paks, cache or self.cache, self.settings)

    def test_install_root_paks_and_game_root_use_same_cache(self):
        sources = [self.resolve(p) for p in (self.game, self.paks, self.game / 'FortniteGame')]
        self.assertEqual(len({s.root for s in sources}), 1)
        self.assertEqual({s.paks for s in sources}, {self.paks})
        self.assertFalse(self.cache.exists(), 'Resolution must be read-only')

    def test_archive_update_changes_cache(self):
        old = self.resolve().root
        (self.paks / 'chunk.utoc').write_bytes(b'updated archive fixture')
        self.assertNotEqual(old, self.resolve().root)

    def test_dependency_update_changes_cache(self):
        old = self.resolve().root
        (self.private / 'map.usmap').write_bytes(b'updated mappings')
        self.assertNotEqual(old, self.resolve().root)

    def test_sources_are_isolated(self):
        other = self.root / 'OtherPaks'
        other.mkdir()
        (other / 'chunk.pak').write_bytes(b'archive fixture')
        self.assertNotEqual(self.resolve().root, self.resolve(other).root)

    def test_cache_cannot_overlap_installation(self):
        for cache in (self.game, self.game / 'Cache', self.paks / 'Cache', self.root):
            with self.subTest(cache=cache), self.assertRaisesRegex(ValueError, 'separate'):
                self.resolve(cache=cache)

    def test_backend_rejects_unsafe_output_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'separate'):
            backend.backend_settings(self.settings, self.game / 'Unsafe', self.paks)
        self.assertFalse((self.game / 'Unsafe').exists())

    def test_effective_settings_resolve_paths_without_copying_keys(self):
        source = self.resolve()
        before = self.settings.read_bytes()
        effective = backend.backend_settings(self.settings, source.root, source.paks)
        config = json.loads(effective.read_text())
        self.assertEqual(config['paks'], str(self.paks))
        self.assertEqual(config['output'], str(source.root))
        self.assertEqual(Path(config['keyFile']), self.private / 'keys.json')
        self.assertEqual(Path(config['mappings']), self.private / 'map.usmap')
        self.assertNotIn('keys', config)
        self.assertNotIn('extra_private_data', config)
        self.assertEqual(before, self.settings.read_bytes())

    def test_legacy_library_needs_no_extractor(self):
        library = self.root / 'Library'
        (library / 'Exports').mkdir(parents=True)
        (library / 'Models').mkdir()
        source = backend.resolve_source(library)
        self.assertEqual(source.root, library)
        self.assertIsNone(source.paks)
        self.settings.write_text(json.dumps({'output': '../Library'}))
        self.assertEqual(backend.backend_settings(self.settings, library), self.settings)
        with self.assertRaisesRegex(ValueError, 'must match'):
            backend.backend_settings(self.settings, self.cache)

    def test_invalid_folder_does_not_create_output(self):
        with self.assertRaisesRegex(ValueError, 'No Fortnite'):
            self.resolve(self.private)
        self.assertFalse(self.cache.exists())

    def test_default_cache_is_outside_installation(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.cache), 'XDG_CACHE_HOME': str(self.cache)}):
            source = backend.resolve_source(self.paks, settings=self.settings)
        self.assertTrue(source.root.is_relative_to(self.cache))

    def test_run_backend_passes_generated_config_without_shell(self):
        source = self.resolve()
        exe = self.private / 'bridge.exe'
        exe.write_bytes(b'fixture')
        with patch.object(backend.subprocess, 'run') as run:
            run.return_value.returncode = 0
            backend.run_backend(exe, self.settings, source.root, 'export', 'Figure/Test', paks=source.paks)
        args = run.call_args.args[0]
        self.assertEqual(args[1], 'export')
        self.assertEqual(args[-1], 'Figure/Test')
        self.assertEqual(Path(args[2]), source.root / 'workshop-extractor-settings.json')
        self.assertFalse(run.call_args.kwargs['shell'])


if __name__ == '__main__':
    unittest.main()
