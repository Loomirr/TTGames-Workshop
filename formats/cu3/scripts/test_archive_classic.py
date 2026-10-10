"""Constructed classic DAT version, hash-routing and traversal regressions."""
import struct
import contextlib
import io
import json
import tempfile
from pathlib import Path
import unittest
from test_archive_v5 import fixture, _path_hash
from archive_v5_fixture.archive_v5 import _parse_index


def classic(layout):
    src=fixture()
    n=5
    raw=bytearray(src[:44]);struct.pack_into('<i',raw,0,layout)
    for i in range(n):raw.extend(src[44+i*12:44+i*12+8])
    raw.extend(src[44+n*12:])
    return raw


class ClassicArchives(unittest.TestCase):
    def test_cli_index_is_read_only_and_refuses_output_reuse(self):
        from archive_index_classic import main
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'GAME.DAT';output=root/'report.json'
            index=classic(-2)
            original=struct.pack('<II',1024,len(index))+bytes(1016)+index
            source.write_bytes(original)
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(source),str(output),'--game','LB1'])
            self.assertEqual(len(json.loads(output.read_text())['entries']),2)
            report=output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                main([str(source),str(output),'--game','LB1'])
            self.assertEqual(output.read_bytes(),report)
            self.assertEqual(source.read_bytes(),original)

    def test_cli_wrong_profile_creates_no_output(self):
        from archive_index_classic import main
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'GAME.DAT';output=root/'report.json'
            index=classic(-2)
            source.write_bytes(struct.pack('<II',1024,len(index))+bytes(1016)+index)
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                main([str(source),str(output),'--game','LB2'])
            self.assertFalse(output.exists())

    def test_known_layouts(self):
        for layout in (-2,-3,-4):
            result=_parse_index(classic(layout),1024,layout=layout)
            self.assertEqual([r['path'] for r in result],['chars/one.cd','cut/TWO.TEX'])

    def test_tcs_hash_order_is_not_leaf_ordinal(self):
        raw=classic(-3);a,b=raw[-16:-12],raw[-12:-8];raw[-16:-12],raw[-12:-8]=b,a
        result=_parse_index(raw,1024,layout=-3)
        self.assertEqual([r['path'] for r in result],['cut/TWO.TEX','chars/one.cd'])
        struct.pack_into('<i',raw,0,-2)
        with self.assertRaisesRegex(ValueError,'hash'):_parse_index(raw,1024,layout=-2)

    def test_version_specific_offset_bits(self):
        for layout,expected in ((-2,0x245),(-3,0x245),(-4,0x200)):
            raw=classic(layout);struct.pack_into('<I',raw,20,0x12344500)
            self.assertEqual(_parse_index(raw,1024,layout=layout)[0]['offset'],expected)

    def test_wrong_layout_traversal_and_bounds(self):
        for layout in (-2,-3,-4):
            raw=classic(layout)
            with self.assertRaisesRegex(ValueError,'version'):_parse_index(raw,1024)
            with self.assertRaises(ValueError):_parse_index(raw[:-2],1024,layout=layout)
            struct.pack_into('<I',raw,8,1000)
            with self.assertRaisesRegex(ValueError,'extent'):_parse_index(raw,1024,layout=layout)

    def test_hash_and_tree_corruption_remain_rejected(self):
        for layout in (-2,-3,-4):
            raw=classic(layout);raw[-16]^=1
            with self.assertRaises(ValueError):_parse_index(raw,1024,layout=layout)
            raw=classic(layout);struct.pack_into('<h',raw,44+3*8+2,3)
            with self.assertRaisesRegex(ValueError,'Cyclic'):_parse_index(raw,1024,layout=layout)


if __name__=='__main__':unittest.main()
