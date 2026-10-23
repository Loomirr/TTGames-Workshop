"""LB2-era skeletal writes preserve tree byte order, block family and details."""
import hashlib
import struct
import unittest
from test_an4_standalone import tree as modern_tree
from test_lb2_an4 import tree
from tt_an4_test.an4 import AnimationFile
from tt_an4_test.an4_edit import patch_record, encode_samples
from tt_an4_test.animation_details import detail_tracks
from tt_an4_test.cu3 import FormatError
from tt_an4_test.tt_deflate import compress, decompress


class LegacyEdits(unittest.TestCase):
    def test_observed_lotr_and_dimensions_trees_keep_version(self):
        for version in (8,11,17):
            raw=modern_tree();struct.pack_into('>I',raw,0,version);raw=bytes(raw)
            rows=[[[.1,0,0,0,0,0]],[[.2,0,0,0,.25,0]]]
            edited,report=patch_record(raw,'Actor',0,rows,hashlib.sha256(raw).hexdigest())
            parsed=AnimationFile('edited',data=edited)
            self.assertEqual(parsed.version,version)
            self.assertEqual(report['animation_variant'],'ANID')
            self.assertEqual(report['byte_order'],'>')
            animation=parsed.actors[0]['records'][0]['animation'];animation.prepare(scene_channels=True)
            self.assertAlmostEqual(animation.sample(1)[0][4],.25,places=4)

    def test_original_family_endian_and_compression_survive(self):
        for endian, versions in (('<', (1,2)), ('>', (2,4,5,6,7))):
            for version in versions:
                for magic in (b'ANIB',b'ANID'):
                    with self.subTest(endian=endian,version=version,magic=magic):
                        raw=tree(endian,version,magic,roots=1)
                        source=AnimationFile('source',data=raw)
                        old=source.actors[0]['records'][0]['animation']
                        rows=[[[.25,2.5,0,0,0,0]],[[.5,2.5,0,0,.3,0]]]
                        stored=compress(raw)
                        result,report=patch_record(stored,'Actor',0,rows,hashlib.sha256(stored).hexdigest())
                        parsed=AnimationFile('result',data=result)
                        new=parsed.actors[0]['records'][0]['animation'];new.prepare(scene_channels=True)
                        self.assertTrue(result.startswith(b'Deflate_v1.0'))
                        self.assertEqual((parsed.version,parsed.endian,new.variant),(version,endian,magic.decode()))
                        self.assertEqual(new.node_flags,old.node_flags)
                        self.assertEqual(parsed.actors[0]['records'][0]['matrix'],source.actors[0]['records'][0]['matrix'])
                        self.assertEqual(parsed.data[8:old.at],raw[8:old.at])
                        self.assertEqual(struct.unpack_from(endian+'I',decompress(result),4)[0],len(parsed.data))
                        for frame in range(2):
                            for got,want in zip(new.sample(frame)[0],rows[frame][0]):
                                self.assertAlmostEqual(got,want,places=4)

    def test_detail_tables_are_preserved_in_both_byte_orders(self):
        for endian in ('<','>'):
            raw=bytearray(tree(endian,2,b'ANIB',roots=1))
            source=AnimationFile('source',data=raw)
            at=source.actors[0]['records'][0]['animation'].at
            raw.extend(bytes((-len(raw))%4));table=len(raw)
            raw.extend(struct.pack(endian+'2HI3I',3,0,table+8-at,0,0,table+20-at))
            child,_=encode_samples([[[0]*6],[[.1,0,0,0,0,0]]],[3],endian=endian,variant='ANIB')
            raw.extend(child)
            struct.pack_into(endian+'I',raw,at+60,table-at)
            struct.pack_into(endian+'I',raw,4,len(raw));raw=bytes(raw)
            rows=[[[0]*6],[[.4,0,0,0,0,0]]]
            result,_=patch_record(raw,'Actor',0,rows,hashlib.sha256(raw).hexdigest(),detail_samples={2:rows})
            self.assertEqual(result[table:table+20],raw[table:table+20])
            tracks=detail_tracks(AnimationFile('edited',data=result).actors[0]['records'][0]['animation'])
            self.assertEqual([t.at for t in tracks],[at,at,table+20])
            for t in tracks:
                t.prepare(scene_channels=True)
                self.assertEqual((t.variant,t.endian),('ANIB',endian))
                self.assertAlmostEqual(t.sample(1)[0][0],.4,places=4)
            for pointer in (4,len(raw)+100):
                bad=bytearray(raw);struct.pack_into(endian+'I',bad,table+4,pointer);bad=bytes(bad)
                with self.assertRaises(FormatError):
                    patch_record(bad,'Actor',0,rows,hashlib.sha256(bad).hexdigest(),detail_samples={2:rows})

    def test_modern_ani_b_and_unrecognized_writer_profiles_stay_refused(self):
        raw=modern_tree();raw[224:228]=b'ANIB';raw=bytes(raw)
        with self.assertRaisesRegex(FormatError,'inspected but not rewritten'):
            patch_record(raw,'Actor',0,[[[0]*6]]*2,hashlib.sha256(raw).hexdigest())
        for kwargs in ({'endian':'='},{'variant':'ANIE'}):
            with self.assertRaises(FormatError):encode_samples([[[0]*6]],[3],**kwargs)


if __name__=='__main__':unittest.main()
