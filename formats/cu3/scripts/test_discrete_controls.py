"""Portable regression for observed LB3/LMSH1 actor and attachment controls."""
import importlib.util,struct,sys,types,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('cu3_control_fixture');package.__path__=[str(root)];sys.modules[package.__name__]=package
from cu3_control_fixture.cu3 import Animation,Reader,FormatError
from cu3_control_fixture.cinematic import visibility


def fixture(channels, flags=0xac):
    kinds=({1:(8,),2:(8,8)}[channels] if channels<3 else
           (14,)*6+{8:(8,8),9:(8,10,10),10:(8,8,10,10)}[channels])
    controls=channels if channels<3 else channels-6
    stride=controls*4;types_at=88;keys_at=(types_at+channels*2+3)&~3;flags_at=keys_at+2*stride
    data=bytearray(flags_at+1);data[:4]=b'DINA'
    struct.pack_into('<6H',data,4,1,2,stride,2,channels,0)
    data[17]=4;data[19]=flags;struct.pack_into('<H',data,22,2)
    struct.pack_into('<2f',data,28,-16,1);struct.pack_into('<9I',data,36,0,80,types_at,keys_at,flags_at,0,0,0,0)
    struct.pack_into('<2f',data,72,1,0);struct.pack_into('<4h',data,80,1,0,-1,-2)
    struct.pack_into(f'<{channels}H',data,types_at,*kinds)
    block=bytes([0,1,0,1]+([2]*4*(controls-2)+[3]*4 if controls>1 else []))
    assert len(block)==stride
    data[keys_at:flags_at]=block*2
    return data


class DiscreteControls(unittest.TestCase):
    def test_translated_visibility_and_resource_controls(self):
        # Three compressed translation curves plus visibility and two resource
        # controls. This is an outer scene track, not a nine-channel pose.
        kinds=(7,7,7,14,14,14,8,10,10)
        scales_at,constants_at,types_at,keys_at,stride=80,104,112,132,36
        flags_at=keys_at+2*stride
        raw=bytearray(flags_at+1);raw[:4]=b'DINA'
        struct.pack_into('<6H',raw,4,1,2,stride,2,9,0)
        raw[17]=4;raw[19]=0xac;raw[flags_at]=2
        struct.pack_into('<H',raw,22,2)
        struct.pack_into('<9I',raw,36,scales_at,constants_at,types_at,keys_at,flags_at,0,0,0,0)
        struct.pack_into('<2f',raw,72,1,0)
        struct.pack_into('<6f',raw,scales_at,1,0,1,0,1,0)
        struct.pack_into('<4h',raw,constants_at,1,0,-1,-2)
        struct.pack_into('<9H',raw,types_at,*kinds)
        block=b''.join(struct.pack('<4H',v,0,0,0) for v in (10,20,30))+bytes([0,1,0,1]+[2]*4+[3]*4)
        raw[keys_at:flags_at]=block*2
        anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertTrue(anim.discrete_scene_controls)
        self.assertEqual(anim.sample(0)[0],[10,20,30,0,0,0,1,-1,-2])
        self.assertEqual(visibility(types.SimpleNamespace(frames=2),{'parent':None,'visibility_animation':anim}),[True,False])
        # An unknown auxiliary type or flag combination must not gain support.
        for bad in ('type','flags'):
            changed=bytearray(raw)
            if bad=='type':struct.pack_into('<H',changed,types_at+16,11)
            else:changed[flags_at]=3
            with self.assertRaises(FormatError):
                Animation(Reader(changed),0,len(changed)).prepare(scene_channels=True)

    def test_resource_pair_has_no_visibility_channel(self):
        raw=fixture(8)
        struct.pack_into('<2H',raw,88+12,10,10)
        struct.pack_into('<2h',raw,80,-1,-1)
        anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertIsNone(anim.control_visibility_channel)
        self.assertEqual(anim.sample(0)[0][6:],[-1,-2])
        self.assertEqual(visibility(types.SimpleNamespace(frames=2),{'parent':None,'visibility_animation':anim}),[True,True])

    def test_attachment_visibility_and_unknown_auxiliary(self):
        for channels in (1,2):
            for flags in (0xa4,0xac):
                raw=fixture(channels,flags);anim=Animation(Reader(raw),0,len(raw))
                actor={'parent':None,'visibility_animation':anim}
                self.assertEqual(visibility(types.SimpleNamespace(frames=2),actor),[True,False])
                if channels==2:self.assertEqual(anim.sample(0)[0][1],-2)

    def test_attachment_unknown_pattern_and_non_boolean_rejected(self):
        raw=fixture(2);struct.pack_into('<H',raw,90,6)
        with self.assertRaisesRegex(FormatError,'two-channel'):
            Animation(Reader(raw),0,len(raw)).prepare(scene_channels=True)
        raw=fixture(1);struct.pack_into('<h',raw,80,25)
        with self.assertRaisesRegex(FormatError,'Non-boolean'):
            visibility(types.SimpleNamespace(frames=2),{'parent':None,'visibility_animation':Animation(Reader(raw),0,len(raw))})

    def test_attachment_visibility_intersects_parent(self):
        raw=fixture(2);anim=Animation(Reader(raw),0,len(raw))
        hidden=fixture(1);struct.pack_into('<h',hidden,80,0)
        parent={'parent':None,'visibility_animation':Animation(Reader(hidden),0,len(hidden))}
        child={'parent':0,'visibility_animation':anim}
        cut=types.SimpleNamespace(frames=2,actors=[parent,child])
        self.assertEqual(visibility(cut,child),[False,False])

    def test_visibility_and_extra_fields_are_not_scale(self):
        for channels in (8,9,10):
            raw=fixture(channels);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
            self.assertTrue(anim.discrete_scene_controls)
            self.assertEqual(anim.sample(0)[0][6],1)
            self.assertEqual(anim.sample(1)[0][6],0)
            self.assertEqual(anim.sample(0)[0][7:],[-1]*(channels-8)+[-2])
            cut=types.SimpleNamespace(frames=2,actors=[])
            self.assertEqual(visibility(cut,{'parent':None,'visibility_animation':anim}),[True,False])

    def test_unknown_pattern_rejected(self):
        for channels in (8,9):
            raw=fixture(channels);struct.pack_into('<H',raw,88+7*2,11)
            anim=Animation(Reader(raw),0,len(raw))
            with self.assertRaises(FormatError):anim.prepare(scene_channels=True)

    def test_bad_integer_reference_rejected(self):
        raw=fixture(9);keys=struct.unpack_from('<I',raw,48)[0];raw[keys+4]=255
        anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        with self.assertRaisesRegex(FormatError,'integer curve'):anim.sample(0)

    def test_non_boolean_control_not_guessed_as_visibility(self):
        raw=fixture(9);struct.pack_into('<h',raw,80,25)
        anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertEqual(anim.sample(0)[0][6],25)
        with self.assertRaisesRegex(FormatError,'Non-boolean'):
            visibility(types.SimpleNamespace(frames=2),{'parent':None,'visibility_animation':anim})


if __name__=='__main__':unittest.main()
