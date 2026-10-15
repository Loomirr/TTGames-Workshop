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


def lsw2():
    # -1 (LSW2 PC): no hash table or trailer, plain byte offsets, stored entries only.
    raw=classic(-1);del raw[-16:]
    struct.pack_into('<4I',raw,8,0x800,4,4,0)
    struct.pack_into('<4I',raw,24,0x1000,8,8,0)
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

    def test_lsw2_plain_offsets_without_hash_table(self):
        result=_parse_index(lsw2(),0x2000,layout=-1)
        self.assertEqual([(r['path'],r['offset'],r['size']) for r in result],
                         [('chars/one.cd',0x800,4),('cut/TWO.TEX',0x1000,8)])

    def test_lsw2_layout_is_never_inferred(self):
        with self.assertRaisesRegex(ValueError,'version'):_parse_index(lsw2(),0x2000,layout=-2)
        raw=classic(-2);struct.pack_into('<i',raw,0,-1)
        with self.assertRaisesRegex(ValueError,'trailer'):_parse_index(raw,1024,layout=-1)
        with self.assertRaisesRegex(ValueError,'trailer'):_parse_index(lsw2()+bytes(8),0x2000,layout=-1)

    def test_lsw2_compressed_or_flagged_entries_refused(self):
        for flags in (2,0x100):
            raw=lsw2();struct.pack_into('<I',raw,36,flags)
            with self.assertRaisesRegex(ValueError,'only stored'):_parse_index(raw,0x2000,layout=-1)

    def test_lsw2_overlap_bounds_and_ordinals_rejected(self):
        raw=lsw2();struct.pack_into('<I',raw,24,0x802)
        with self.assertRaisesRegex(ValueError,'Overlapping'):_parse_index(raw,0x2000,layout=-1)
        with self.assertRaisesRegex(ValueError,'extent'):_parse_index(lsw2(),0x1004,layout=-1)
        raw=lsw2();struct.pack_into('<h',raw,44+4*8,0)
        with self.assertRaisesRegex(ValueError,'ordinal'):_parse_index(raw,0x2000,layout=-1)
        raw=lsw2();struct.pack_into('<h',raw,44+3*8+2,3)
        with self.assertRaisesRegex(ValueError,'Cyclic'):_parse_index(raw,0x2000,layout=-1)

    def test_cli_lsw2_profile(self):
        from archive_index_classic import main
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'game.dat';output=root/'report.json'
            index=lsw2()
            original=struct.pack('<II',0x2000,len(index))+bytes(0x2000-8)+index
            source.write_bytes(original)
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(source),str(output),'--game','LSW2'])
            report=json.loads(output.read_text())
            self.assertEqual((report['layout'],len(report['entries'])),(-1,2))
            self.assertEqual(source.read_bytes(),original)

    def test_hash_and_tree_corruption_remain_rejected(self):
        for layout in (-2,-3,-4):
            raw=classic(layout);raw[-16]^=1
            with self.assertRaises(ValueError):_parse_index(raw,1024,layout=layout)
            raw=classic(layout);struct.pack_into('<h',raw,44+3*8+2,3)
            with self.assertRaisesRegex(ValueError,'Cyclic'):_parse_index(raw,1024,layout=layout)


if __name__=='__main__':unittest.main()
