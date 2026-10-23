"""Fresh loose-tree discovery and identity-checked archive index reuse."""
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.asset_index import AssetIndex
from io_scene_lego_cu3 import archive_assets as aa
from io_scene_lego_cu3.cu3 import FormatError
from test_archive_assets import archive


class AssetEnumeration(unittest.TestCase):
    def test_fresh_nested_discovery_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'chars').mkdir()
            (root / 'chars' / 'Hero.CD').write_bytes(b'first')
            (root / 'ignored.bin').write_bytes(b'ignored')
            first = AssetIndex(root)
            self.assertEqual(first.find_exact('chars/hero.cd'), root / 'chars' / 'Hero.CD')
            (root / 'Hero.CD').write_bytes(b'other')
            second = AssetIndex(root)
            self.assertEqual(sum(map(len, second.files.values())), 2)
            with self.assertRaisesRegex(FormatError, 'Ambiguous'):
                second.find('Hero.CD')
            (root / 'chars' / 'Hero.CD').unlink()
            self.assertIsNone(AssetIndex(root).find_exact('chars/hero.cd', required=False))

    def test_file_links_and_directory_cycles(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder); root = parent / 'assets'; root.mkdir()
            inside = root / 'real.cd'; inside.write_bytes(b'inside')
            outside = parent / 'outside.cd'; outside.write_bytes(b'outside')
            try:
                (root / 'safe.cd').symlink_to(inside)
                (root / 'escape.cd').symlink_to(outside)
                (root / 'cycle').symlink_to(root, target_is_directory=True)
            except OSError as error:
                self.skipTest(f'Link creation unavailable: {error}')
            assets = AssetIndex(root)
            self.assertEqual(set(assets.files), {'real.cd', 'safe.cd'})
            (root / 'safe.cd').unlink()
            (root / 'safe.cd').symlink_to(outside)
            with self.assertRaisesRegex(FormatError, 'escapes'):
                assets.find('safe.cd')


class ArchiveIndexReuse(unittest.TestCase):
    def setUp(self):
        aa._INDEX_CACHE.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'; self.game.mkdir()
        self.path = self.game / 'GAME.DAT'
        archive(self.path)

    def tearDown(self):
        aa._INDEX_CACHE.clear()
        self.temp.cleanup()

    def provider(self):
        return aa.ArchiveAssetIndex(self.game, 'LB3', self.root / 'cache')

    def test_reuses_metadata_without_sharing_mutable_entries_or_budgets(self):
        with patch.object(aa, 'index_v6', wraps=aa.index_v6) as reader:
            first = self.provider()
            first.find('SAMPLE.CD')
            first.files['sample.cd'][0][1]['size'] = 999
            second = self.provider()
            self.assertEqual(reader.call_count, 1)
            self.assertEqual(second.files['sample.cd'][0][1]['size'], 3)
            self.assertEqual(second._decoded_total, 0)
            self.assertEqual(second.events, [])
            self.assertEqual(second.find('SAMPLE.CD').read_bytes(), b'abc')

    def test_changed_archive_reparsed_and_old_provider_refuses(self):
        with patch.object(aa, 'index_v6', wraps=aa.index_v6) as reader:
            first = self.provider()
            archive(self.path, b'changed', name='NEW.CD')
            second = self.provider()
            self.assertEqual(reader.call_count, 2)
            self.assertEqual(set(second.files), {'new.cd'})
            with self.assertRaisesRegex(FormatError, 'Archive changed'):
                first.find('SAMPLE.CD')

    def test_change_during_index_read_is_not_cached(self):
        original = aa.index_v6
        def changing(path):
            result = original(path)
            archive(path, b'changed')
            return result
        with patch.object(aa, 'index_v6', side_effect=changing):
            with self.assertRaisesRegex(FormatError, 'while its index'):
                self.provider()
        self.assertFalse(aa._INDEX_CACHE)

    def test_profile_is_part_of_cache_key_and_size_bound_is_enforced(self):
        stamp = aa._path_archive_stamp(self.path)
        with patch.object(aa, '_INDEX_CACHE_ENTRIES', 1):
            calls = []
            def read(path):
                calls.append(path)
                return [{'path': 'a'}, {'path': 'b'}]
            aa._cached_index(self.path, 'LB3', stamp, read)
            aa._cached_index(self.path, 'LB3', stamp, read)
            self.assertEqual(len(calls), 2)
            self.assertFalse(aa._INDEX_CACHE)
        aa._cached_index(self.path, 'LB3', stamp, lambda p: [{'path': 'a'}])
        result = aa._cached_index(self.path, 'HOBBIT', stamp, lambda p: [{'path': 'b'}])
        self.assertEqual(result[0]['path'], 'b')

    def test_cache_has_an_archive_count_limit(self):
        paths = []
        for number in range(10):
            path = self.game / f'DLC{number}.DAT'; path.write_bytes(b'fixture')
            paths.append(path)
            aa._cached_index(path, 'LB3', aa._path_archive_stamp(path), lambda p: [{'path': 'a'}])
        self.assertEqual(len(aa._INDEX_CACHE), 8)
        self.assertFalse(any(key[0] in paths[:2] for key in aa._INDEX_CACHE))


if __name__ == '__main__':
    unittest.main()
