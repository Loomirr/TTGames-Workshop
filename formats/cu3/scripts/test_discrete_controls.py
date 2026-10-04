"""Portable regression for observed LB3 eight/nine/ten-channel control tracks."""
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
