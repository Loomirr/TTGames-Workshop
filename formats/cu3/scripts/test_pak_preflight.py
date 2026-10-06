"""Asset-free PAK preflight/publication regressions; no external decoder runs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(ROOT / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.animation_bank import AnimationBank
from io_scene_lego_cu3.pak_reader import parse_pak, read_pak, MAX_DECODED
from io_scene_lego_cu3.archive_paths import preflight_destination
from io_scene_lego_cu3.cu3 import FormatError

SCRIPT = ROOT / 'formats/an4/lmsh1/unpack_pak.py'
spec = importlib.util.spec_from_file_location('pak_cli_fixture', SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def wrapper(payload, expected=None):
    return (b'Deflate_v1.0'.ljust(32, b'\0') + struct.pack('<I', len(payload) if expected is None else expected)
            + b'\x05' + struct.pack('<H', len(payload)) + payload)


def pak(*members):
    table_end = 24 + len(members) * 28
    names = bytearray()
    offsets = []
    for name, _ in members:
        offsets.append(table_end + len(names))
        names.extend(name.encode('ascii') + b'\0')
    data = bytearray(table_end) + names
    for i, ((name, payload), name_at) in enumerate(zip(members, offsets)):
        offset = len(data)
        data.extend(payload)
        struct.pack_into('<7I', data, 24 + i * 28, name_at, offset, len(payload), 1, 0, 0, 0)
    struct.pack_into('<6I', data, 0, 0x1234567A, len(members), len(data), 0, 0, 0)
    return data


class PakPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.pak'
        self.destination = self.root / 'out'

    def reject_before_decode(self, raw):
        self.source.write_bytes(raw)
        with patch.object(cli, 'decompress') as decode, patch.object(cli, 'publish_bundle') as publish, \
                patch.object(subprocess, 'run') as backend:
            with self.assertRaises((ValueError, FileExistsError)):
                cli.unpack(self.source, self.destination, self.root / 'quickbms', self.root / 'ttgames.bms')
            decode.assert_not_called()
            publish.assert_not_called()
            backend.assert_not_called()
        self.assertFalse(self.destination.exists())
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['input.pak'])

    def test_malformed_headers_are_preflight_errors(self):
        for raw in (b'', b'tiny', b'\0' * 24, pak(('good.an4', b'abc'))[:-1]):
            with self.subTest(raw=raw[:24]):
                self.reject_before_decode(raw)

    def test_all_names_checked_before_valid_first_member_decodes(self):
        for name in ('', '.', '..', '/escape', 'C:/escape', '//server/share', 'a/../b', 'a/./b',
                     'a//b', 'a\\..\\b', 'CON', 'CON.txt', 'NUL .txt', 'COM1.an4', 'LPT9.txt',
                     'dir/file:stream', 'dir/last.', 'dir/last ', 'bad\nname', 'bad\x7fname'):
            with self.subTest(name=name):
                self.reject_before_decode(pak(('first.an4', wrapper(b'abc')), (name, b'xyz')))

    def test_duplicates_case_aliases_and_file_directory_collisions(self):
        for first, second in (('A.an4', 'A.an4'), ('A.an4', 'a.AN4'), ('dir/a', 'dir\\a'),
                              ('dir/a', 'DIR/b'), ('a', 'a/b'), ('a/b', 'a')):
            with self.subTest(names=(first, second)):
                self.reject_before_decode(pak((first, b'a'), (second, b'b')))

    def test_manifest_filename_reserved_before_publication(self):
        self.reject_before_decode(pak(('pak-manifest.JSON', wrapper(b'a'))))

    def test_name_cannot_reference_table_or_payload(self):
        for target in (24, 'payload'):
            raw = pak(('safe.an4', b'name\0'))
            offset = struct.unpack_from('<I', raw, 28)[0] if target == 'payload' else target
            struct.pack_into('<I', raw, 24, offset)
            self.reject_before_decode(raw)

    def test_payload_extent_and_partial_overlap_rejected(self):
        raw = pak(('one.an4', b'1234'), ('two.an4', b'5678'))
        for field, value in ((28, 24), (32, len(raw)), (56, struct.unpack_from('<I', raw, 28)[0] + 1)):
            bad = raw[:]
            struct.pack_into('<I', bad, field, value)
            self.reject_before_decode(bad)

    def test_unterminated_name_rejected(self):
        raw = pak(('name', b'payload'))
        raw[struct.unpack_from('<I', raw, 24)[0]:] = b'x' * (len(raw) - struct.unpack_from('<I', raw, 24)[0])
        self.reject_before_decode(raw)

    def test_wrapper_and_advertised_size_rejected_before_decode(self):
        for body in (b'Deflate_v1.0', wrapper(b'a', MAX_DECODED + 1), wrapper(b'a', 0),
                     b'Deflate_v1.0' + b'x' * 30):
            with self.subTest(body=body[:36]):
                self.reject_before_decode(pak(('clip.an4', body)))

    def test_packed_decoded_and_cumulative_limits(self):
        raw = pak(('one.an4', wrapper(b'123')), ('two.an4', wrapper(b'456')))
        for limits in ({'max_packed': len(raw) - 1}, {'max_decoded': 2}, {'max_total': 5}):
            with self.subTest(limits=limits), self.assertRaises(FormatError):
                parse_pak(raw, **limits)
        self.source.write_bytes(raw)
        with self.assertRaises(FormatError):
            read_pak(self.source, max_packed=len(raw) - 1)

    def test_existing_destination_is_preserved_before_decoding(self):
        self.source.write_bytes(pak(('clip.an4', wrapper(b'abc'))))
        self.destination.mkdir()
        previous = self.destination / 'keep.txt'
        previous.write_bytes(b'previous')
        with patch.object(cli, 'decompress') as decode, self.assertRaises(FileExistsError):
            cli.unpack(self.source, self.destination)
        decode.assert_not_called()
        self.assertEqual(previous.read_bytes(), b'previous')

    def test_parent_symlink_and_case_alias_rejected(self):
        self.source.write_bytes(pak(('clip.an4', b'abc')))
        external = self.root / 'external'
        external.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            cli.unpack(self.source, link / 'out')
        self.assertEqual(list(external.iterdir()), [])
        upper = self.root / 'OUTPUT'
        upper.mkdir()
        with self.assertRaises((ValueError, FileExistsError)):
            preflight_destination(self.root / 'output', ['file'], require_absent=True)

    def test_success_uses_internal_decoder_and_verified_manifest(self):
        original = pak(('Anims/Clip.an4', wrapper(b'abc')), ('metadata.txt', b'test'))
        self.source.write_bytes(original)
        with patch.object(subprocess, 'run') as backend:
            report = cli.unpack(self.source, self.destination, 'missing-quickbms', 'missing-bms')
            backend.assert_not_called()
        self.assertEqual((self.destination / 'Anims/Clip.an4').read_bytes(), b'abc')
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(report['count'], 2)
        self.assertEqual(len(report['entries']), 2)
        self.assertEqual(report, json.loads((self.destination / 'pak-manifest.json').read_text()))
        self.assertEqual(report['entries'][0]['sha256'], hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(set(path.name for path in self.root.iterdir()), {'input.pak', 'out'})

    def test_second_decode_failure_cleans_staging_without_publication(self):
        self.source.write_bytes(pak(('one', b'ok'), ('two', wrapper(b'a', 2))))
        with self.assertRaisesRegex(FormatError, 'size mismatch'):
            cli.unpack(self.source, self.destination)
        self.assertEqual([path.name for path in self.root.iterdir()], ['input.pak'])
        self.source.write_bytes(pak(('one', b'ok'), ('two', wrapper(b'ab'))))
        cli.unpack(self.source, self.destination)
        self.assertEqual((self.destination / 'two').read_bytes(), b'ab')

    def test_nested_wrappers_remain_rejected(self):
        self.source.write_bytes(pak(('clip.an4', wrapper(wrapper(b'abc')))))
        with self.assertRaisesRegex(FormatError, 'Nested'):
            cli.unpack(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(FormatError, 'Nested'):
            AnimationBank(self.source).read('clip.an4')

    def test_bank_reuses_preflight_and_preserves_source_names(self):
        raw = pak(('Anims\\Clip.an4', wrapper(b'abc')))
        bank = AnimationBank('fixture.pak', data=raw)
        self.assertEqual(bank.entries['anims/clip.an4']['name'], 'Anims/Clip.an4')
        self.assertEqual(bank.read('ANIMS/CLIP.AN4'), b'abc')
        with self.assertRaises(FormatError):
            AnimationBank('fixture.pak', data=pak(('NUL.an4', b'a')))

    def test_cli_has_no_blender_requirement_and_preflights_entire_batch(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no external tool', result.stdout)
        source_dir = self.root / 'sources'
        source_dir.mkdir()
        (source_dir / 'a.pak').write_bytes(pak(('clip.an4', wrapper(b'abc'))))
        (source_dir / 'z.PAK').write_bytes(pak(('../escape', b'abc')))
        result = subprocess.run([sys.executable, str(SCRIPT), str(source_dir), str(self.destination)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
