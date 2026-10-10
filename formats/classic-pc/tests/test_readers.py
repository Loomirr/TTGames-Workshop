"""Bounds and format separation checks, with constructed data only."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from an3 import An3
from cu2 import Block,Cutscene,UnsupportedVersion,script_fps
import giz


def constant_block(tag=b'4INA'):
    d=bytearray(112);d[:4]=tag
    struct.pack_into('<6H',d,4,1,3,0,3,9,0)
    struct.pack_into('<ff',d,28,2.0,0.5)
    struct.pack_into('<5I',d,36,0,80,82,0,104)
    struct.pack_into('<H',d,80,4)
    struct.pack_into('<9H',d,82,*([16]*9))
    return d


def pickup_file(version=4,count=1,extra=b''):
    header=struct.pack('<3I',version,count,0)+(struct.pack('<2f',10,1) if version in (5,6,7) else b'')
    record=struct.pack('<8s3f3B',b'Pickup',1,2,3,ord('s'),0,0) if count else b''
    body=header+record+extra;name=b'GizmoPickup'
    return struct.pack('<II',1,len(name))+name+struct.pack('<I',len(body))+body+struct.pack('<I',0)


class ReaderTests(unittest.TestCase):
    def test_constant_only_null_key_pointer_is_valid(self):
        block=Block(constant_block(),0)
        self.assertEqual(block.pose(2),[(4.0,)*9])

    def test_an4_and_unknown_tags_are_not_classic_an3(self):
        for tag in (b'ANID',b'9INA',b'ANIB'):
            with self.assertRaises(ValueError):An3('constructed',data=constant_block(tag))

    def test_an3_is_not_an_arbitrary_cu2_root_track(self):
        d=constant_block();struct.pack_into('<H',d,12,7)
        with self.assertRaises(ValueError):An3('constructed',data=d)

    def test_invalid_constant_reference_refused_before_sampling(self):
        d=constant_block();struct.pack_into('<H',d,82,19)
        with self.assertRaisesRegex(ValueError,'constant index'):Block(d,0)

    def test_truncated_and_nonfinite_tables_refused(self):
        with self.assertRaises(ValueError):Block(constant_block()[:88],0)
        d=constant_block();struct.pack_into('<f',d,28,float('nan'))
        with self.assertRaisesRegex(ValueError,'non-finite'):Block(d,0)

    def test_invalid_moving_key_count_refused(self):
        d=constant_block();struct.pack_into('<H',d,8,4)
        with self.assertRaises(ValueError):Block(d,0)

    def test_unknown_cu2_version_is_always_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scene.cu2';d=bytearray(112)
            struct.pack_into('<II',d,0,518,4096);struct.pack_into('<I',d,40,4096)
            path.write_bytes(d)
            with self.assertRaises(UnsupportedVersion):Cutscene(path)

    def test_script_rate_does_not_accept_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scene.txt';path.write_text('fpsec '+('9'*350))
            self.assertIsNone(script_fps(path))

    def test_pickup_versions_and_end_marker(self):
        for version in (4,5,7):
            data=pickup_file(version)
            self.assertIsNone(giz.scan(data)['problem'])
            self.assertEqual(giz.pickup_table(data)['pickups'][0]['pos'],[1,2,3])

    def test_version_six_requires_empty_table(self):
        self.assertEqual(giz.pickup_table(pickup_file(6,0))['count'],0)
        with self.assertRaises(ValueError):giz.pickup_table(pickup_file(6))

    def test_malformed_pickups_and_unknown_versions_stay_refused(self):
        for data in (pickup_file(4,extra=b'x'),pickup_file(8),pickup_file(4)[:-6]):
            with self.assertRaises(ValueError):giz.pickup_table(data)


if __name__=='__main__':unittest.main()
