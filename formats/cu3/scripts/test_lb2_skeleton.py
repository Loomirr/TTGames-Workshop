"""LEGO Batman 2 HGOL 9: the HGOL 10 layout without its opaque block, and its variant fence."""
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

package=types.ModuleType('lb2_skeleton_fixture')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from lb2_skeleton_fixture.cu3 import FormatError
from lb2_skeleton_fixture.skeleton import read_skeleton, scan_skeleton_candidates, select_skeleton

I4=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
NAMES=b'Root\0Layer\0'


def hgol(version, special=0, *, opaque=None):
    raw=b'LOGH'+struct.pack('>2I',version,1)+struct.pack('>I',0)
    raw+=struct.pack('>16f3f2B',*I4,0,0,0,255,0)
    raw+=struct.pack('>I16f',1,*I4)*2
    raw+=struct.pack('>I',0)+struct.pack('>I',1)+struct.pack('>I',0)+struct.pack('>16fB',*I4,0)
    raw+=struct.pack('>IB',1,0)
    if opaque if opaque is not None else version==10:
        raw+=struct.pack('>I',0)
    raw+=struct.pack('>IBBHB',1,0,0,special,0)
    return raw+struct.pack('>I',1)+struct.pack('>I',5)+struct.pack('>3H',0,1,0)


def trailer(threshold, mapping):
    raw=struct.pack('>I',0)+bytes(8)+struct.pack('>6f',-1,-1,-1,1,1,1)+bytes(12)+struct.pack('>f',threshold)
    raw+=struct.pack('>I',1)+b'\0'+struct.pack('>I',1)+b'\0'+struct.pack('>f',1)
    return raw+struct.pack('>I',len(mapping))+b''.join(struct.pack('>H',v) for v in mapping)+b'\0'


def group(fence=b'\0\0\0\0\0ATEM'):
    raw=b'LBTN'+struct.pack('>2I',1,len(NAMES))+NAMES
    raw+=b'5LVI'+struct.pack('>2I',1,0)+b'ROTV'+struct.pack('>I',2)
    raw+=hgol(9,0)+trailer(0,[])+hgol(9,1)+trailer(25,[0])
    return raw+fence


class LB2Skeleton(unittest.TestCase):
    def path(self,data):
        f=tempfile.NamedTemporaryFile(suffix='.ghg',delete=False);f.write(data);f.close()
        self.addCleanup(Path(f.name).unlink)
        return Path(f.name)

    def test_hgol9_has_no_opaque_block(self):
        rig=read_skeleton(self.path(b'LBTN'+struct.pack('>2I',1,len(NAMES))+NAMES+hgol(9)),1)
        self.assertEqual((rig['version'],rig['joints'][0]['name'],rig['layers'][0]['name']),(9,'Root','Layer'))
        self.assertEqual(rig['opaque_tail_hex'],'')
        self.assertNotIn('opaque_length',[s['field'] for s in rig['decoded_section_spans']])

    def test_variant_group_uses_the_lb2_fence(self):
        display=dict(version=14,specials=[dict(index=i,name='Body',parts=[dict(part=i,material=0)],unsupported_commands=[])
                                          for i in range(2)])
        mesh=dict(parts=[dict(vertices=[dict(weights=[(0,1.)])]) for _ in range(2)])
        scan=scan_skeleton_candidates(self.path(group()))
        selected=select_skeleton(scan['candidates'],display=display,mesh=mesh)
        self.assertEqual(selected['selection']['reason'],'verified_native_variant_base')
        self.assertEqual(scan['candidates'][0]['native_variant_group']['version'],9)
        # HGOL 10's fence (flag byte 1) is not accepted for HGOL 9.
        bad=scan_skeleton_candidates(self.path(group(b'\0\0\0\0\1ATEM')))
        self.assertIn('native_variant_error',bad['candidates'][0])


if __name__=='__main__':
    unittest.main()
