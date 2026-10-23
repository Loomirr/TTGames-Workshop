"""Asset-free ANI-D writer checks with nonmonotonic samples and exact trees."""
import hashlib
import struct
import sys
import unittest
from test_an4_standalone import tree
from tt_an4_test.an4 import AnimationFile
from tt_an4_test.cu3 import Animation,Reader,FormatError
from tt_an4_test.an4_edit import encode_samples,patch_record,effective_samples
from tt_an4_test.tt_deflate import compress,decompress


class AN4Edits(unittest.TestCase):
    def test_native_endian_loading_preserves_baked_scalars(self):
        # LMSH1's ANI-D loader sizes the scale swap from the key pointer,
        # not the number of animated curves. A pointer-only decode therefore
        # misses corruption when constants/types are interleaved in that span.
        # Model those observed loading ranges, then consume little-endian data
        # independently of Animation.sample (only writer-emitted types here).
        def loaded_samples(data, at, expected):
            raw = bytearray(data)
            nodes, keys, stride = struct.unpack_from('>3H', data, at+4)
            curves = struct.unpack_from('>H', data, at+12)[0]
            scales, constants, types, groups, flags = (
                at+p for p in struct.unpack_from('>5I', data, at+36))
            count = nodes*curves
            self.assertEqual(data[at+19] & 0x30, 0x10)
            self.assertEqual(data[at+17], 0)  # Writer has no integer prefix.

            def swap(start, width, amount):
                self.assertGreaterEqual(amount, 0)
                self.assertLessEqual(start+width*amount, len(raw))
                for pos in range(start, start+width*amount, width):
                    raw[pos:pos+width] = raw[pos:pos+width][::-1]

            # Order and range are the native loading contract. In particular,
            # swapping this range must not swap the constants a second time.
            swap(scales, 4, 2*((groups-scales)//8))
            swap(constants, 4, (types-constants)//4)
            swap(types, 2, count)
            kinds = struct.unpack_from('<'+str(count)+'H', raw, types)
            self.assertEqual(raw[types+count*2:types+count*3], bytes(count))
            key = groups
            for _ in range((keys+7)//4):
                for kind in kinds:
                    if kind == 7:
                        swap(key, 2, 4)
                        key += 8
                    else:
                        self.assertGreaterEqual(kind, 14)
                        self.assertLess(kind, 16+(types-constants)//4)
            self.assertEqual(key, groups+((keys+7)//4)*stride)
            self.assertEqual(raw[flags:flags+nodes], data[flags:flags+nodes])
            for frame, wanted in enumerate(expected):
                scale, key = scales, groups+frame*stride
                for channel, kind in enumerate(kinds):
                    if kind == 7:
                        multiplier, minimum = struct.unpack_from('<2f', raw, scale)
                        value = struct.unpack_from('<H', raw, key)[0]*multiplier+minimum
                        scale += 8
                        key += 8
                    elif kind < 16:
                        value = kind-14
                    else:
                        value = struct.unpack_from('<f', raw, constants+4*(kind-16))[0]
                    self.assertAlmostEqual(value, wanted[channel//curves][channel%curves], delta=0.0001)

        rows = [[[v, 2.5, 0, 1, -.75, -v, 1, 1.25, 1+v/4]]
                for v in (0, .5, -.25, 1, -.5)]
        block, _ = encode_samples(rows, [0xb], 9)
        with self.subTest(storage='standalone nine-channel block'):
            loaded_samples(block, 0, rows)
        original = bytes(tree())
        rows = [[row[0][:6]] for row in rows[:2]]
        patched, _ = patch_record(original, 'Actor', 0, rows,
                                  hashlib.sha256(original).hexdigest())
        with self.subTest(storage='relocated streams in original AN4 tree'):
            loaded_samples(patched, 224, rows)

    def test_inactive_root_and_scale_groups_stay_absent(self):
        # A local edit must not start driving root placement or previously
        # absent scales. These flags are part of the engine's pose contract.
        neutral=[0,0,0,0,0,0,1,1,1]
        rows=[[neutral[:], [t,0,0,0,.2,0,1,1,1],
               [0,0,0,0,0,0,1+t,1,1]] for t in (0,.1,.2)]
        raw,_=encode_samples(rows,[0,3,8],9)
        anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertEqual(anim.node_flags,(0,3,8))
        self.assertEqual(anim.sample(1)[0],[0]*9)
        self.assertEqual(effective_samples(anim,1)[0],neutral)
        self.assertEqual(effective_samples(anim,1)[1][6:],[1,1,1])
        self.assertAlmostEqual(anim.sample(1)[2][6],1.1,places=4)

    def test_edit_cannot_silently_activate_absent_native_channels(self):
        for flags,channel,value in ((0,0,.1),(2,3,.1),(3,6,1.1)):
            with self.subTest(flags=flags,channel=channel):
                row=[0,0,0,0,0,0,1,1,1];row[channel]=value
                with self.assertRaisesRegex(FormatError,'absent native channel'):
                    encode_samples([[row]],[flags],9)

    def test_older_ani_e_trees_are_inspectable_but_not_rewritten(self):
        from test_lb2_an4 import tree as older_tree
        for endian,version in (('<',1),('<',2),('>',7)):
            raw=older_tree(endian,version,magic=b'ANIE',roots=1)
            self.assertEqual(len(AnimationFile('old.an4',data=raw).actors),1)
            with self.assertRaisesRegex(FormatError,'inspected but not rewritten'):
                patch_record(raw,'Actor',0,[[[0]*6]]*2,hashlib.sha256(raw).hexdigest())

    def test_compressed_source_stays_compressed_after_edit(self):
        raw=bytes(tree());wrapped=compress(raw)
        rows=[[[0,0,0,0,0,0]],[[.1,0,0,0,.2,0]]]
        output,report=patch_record(wrapped,'Actor',0,rows,hashlib.sha256(wrapped).hexdigest())
        self.assertTrue(output.startswith(b'Deflate_v1.0'))
        self.assertEqual(report['storage']['source'],report['storage']['output'])
        self.assertEqual(report['storage']['stored_bytes'],len(output))
        rebuilt=decompress(output)
        self.assertEqual(rebuilt[8:212],raw[8:212])
        parsed=AnimationFile('edited.AN4',data=output)
        anim=parsed.actors[0]['records'][0]['animation'];anim.prepare(scene_channels=True)
        self.assertAlmostEqual(anim.sample(1)[0][4],.2,places=5)
        self.assertEqual(decompress(wrapped),raw)

    def test_unverified_anib_rewrite_is_refused(self):
        raw=tree();raw[224:228]=b'ANIB';raw=bytes(raw)
        with self.assertRaisesRegex(FormatError,'inspected but not rewritten'):
            patch_record(raw,'Actor',0,[[[0]*6]]*2,hashlib.sha256(raw).hexdigest())

    def test_nine_channels_preserve_scale_and_gate_degenerate_scale(self):
        rows=[[[v,0,0,0,0,0,1,1,1]] for v in (0,.1,-.2)]
        raw,error=encode_samples(rows,[0xb],9);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertEqual(anim.curves,9);self.assertEqual(anim.sample(1)[0][6:],[1,1,1])
        rows[0][0][6]=2
        raw,error=encode_samples(rows,[0xb],9);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertAlmostEqual(anim.sample(0)[0][6],2,places=4)
        rows[0][0][6]=0
        with self.assertRaisesRegex(FormatError,'nonzero scale'):encode_samples(rows,[0xb],9)

    def test_auxiliaries_require_explicit_omission(self):
        raw=tree();struct.pack_into('>I',raw,224+60,80);raw=bytes(raw)
        rows=[[[0]*6]]*2;sha=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(FormatError,'detail'):patch_record(raw,'Actor',0,rows,sha)
        output,report=patch_record(raw,'Actor',0,rows,sha,omit_auxiliary=True)
        self.assertEqual(report['omitted_auxiliary_offsets'],[0,80,0,0])

    def test_detail_streams_preserve_original_tables_addresses_and_metadata(self):
        from tt_an4_test.animation_details import detail_tracks
        raw=tree();raw[224+19]=0xe4
        raw[224+16]=9
        struct.pack_into('>H',raw,224+10,0)  # Legacy field differs from current frames.
        raw.extend(bytes((-len(raw))%4));table=len(raw)
        raw.extend(struct.pack('>2H5I',3,0,table+12-224,0x12345678,0,0,24+table-224))
        child,_=encode_samples([[[0]*6],[[.1,0,0,0,0,0]]],[3])
        raw.extend(child)
        struct.pack_into('>I',raw,224+60,table-224)
        struct.pack_into('>I',raw,4,len(raw));raw=bytes(raw)
        before=AnimationFile('original',data=raw)
        original=before.actors[0]['records'][0]['animation']
        tracks=detail_tracks(original)
        self.assertEqual([t.at for t in tracks],[224,224,table+24])
        main=[[[0]*6],[[.5,0,0,0,0,0]]]
        reduced=[[[0]*6],[[.25,0,0,0,0,0]]]
        with self.assertRaisesRegex(FormatError,'require samples'):
            patch_record(raw,'Actor',0,main,hashlib.sha256(raw).hexdigest())
        edited,report=patch_record(raw,'Actor',0,main,hashlib.sha256(raw).hexdigest(),detail_samples={2:reduced})
        result=AnimationFile('edited',data=edited)
        actual=detail_tracks(result.actors[0]['records'][0]['animation'])
        self.assertEqual([t.at for t in actual],[t.at for t in tracks])
        self.assertEqual(edited[table:table+24],raw[table:table+24])
        self.assertEqual(edited[240],9)
        self.assertEqual(edited[234:236],b'\0\0')
        self.assertEqual(actual[0].flags,0xd4)
        actual[0].prepare(scene_channels=True)
        self.assertAlmostEqual(actual[0].sample(1)[0][0],.5,places=5)
        self.assertAlmostEqual(actual[2].sample(1)[0][0],.25,places=5)
        self.assertEqual(report['preserved_detail_slots'],3)
        self.assertEqual(report['omitted_auxiliary_offsets'],[])
        for at,value in ((table,0xffff0000),(table+4,0xffffffff),(table+20,4)):
            bad=bytearray(raw);struct.pack_into('>I',bad,at,value)
            with self.assertRaises(FormatError):
                patch_record(bytes(bad),'Actor',0,main,hashlib.sha256(bad).hexdigest(),detail_samples={2:reduced})
    def test_nonmonotonic_frames_and_fractional_interpolation(self):
        rows=[[[v,3.5,0,1,0,0]] for v in (0,1,-2,4,-1)]
        raw,error=encode_samples(rows,[0x23]);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertLess(error,.0001);self.assertEqual(anim.node_flags,(0x23,))
        for index,frame in enumerate(rows):
            for a,b in zip(anim.sample(index)[0],frame[0]):self.assertAlmostEqual(a,b,places=3)
        self.assertAlmostEqual(anim.sample(.5)[0][0],.5,places=3)

    def test_existing_tree_names_matrix_and_record_pointer(self):
        raw=bytes(tree());rows=[[[0,0,0,0,0,0]],[[.1,0,0,0,.2,0]]]
        output,report=patch_record(raw,'Actor',0,rows,hashlib.sha256(raw).hexdigest())
        parsed=AnimationFile('output.AN4',data=output);actor=parsed.actors[0]
        self.assertEqual(actor['name'],'Actor');self.assertEqual(actor['records'][0]['name'],'Clip')
        self.assertEqual(actor['records'][0]['matrix'],AnimationFile('original.AN4',data=raw).actors[0]['records'][0]['matrix'])
        self.assertEqual(output[8:212],raw[8:212]);self.assertEqual(report['frames'],2)

    def test_rejects_unknown_node_flags_bad_samples_frame_changes_and_hash(self):
        for rows,flags in (([],[3]),([[[0]*6]],[8]),([[[float('nan')]*6]],[3]),([[[0]*7]],[3])):
            with self.assertRaises(FormatError):encode_samples(rows,flags)
        raw=bytes(tree());sha=hashlib.sha256(raw).hexdigest()
        for actor,index,rows,h in (('Unknown',0,[],sha),('Actor',10,[],sha),('Actor',0,[[[0]*6]],sha),('Actor',0,[], 'wrong')):
            with self.assertRaises(FormatError):patch_record(raw,actor,index,rows,h)

if __name__=='__main__':unittest.main()
