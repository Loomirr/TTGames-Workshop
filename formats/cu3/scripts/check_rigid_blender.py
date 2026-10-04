"""Blender-only anchored rigid regression; does not require any game assets."""
import sys
from pathlib import Path
from types import SimpleNamespace
from mathutils import Euler, Matrix, Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Addon'))
from io_scene_lego_cu3.rigid_blender import rigid_samples
from io_scene_lego_cu3.blender_import import C, CI
from io_scene_lego_cu3.cu3 import FormatError


class Track:
    nodes=1;curves=9;node_flags=(11,);keys=2
    descriptors=[{'step':False}]*9
    rows=[[0,0,0,.3,-.2,.1,.8,.8,.8],[.2,0,0,.3,-.2,.1,.8,.8,.8]]
    def prepare(self,**kwargs):pass
    def position(self,frame):return frame
    def sample(self,frame,key_position=None):
        return [self.rows[int(frame if key_position is None else key_position)][:]]


rotation=Euler((-.3,.2,.1),'XYZ').to_quaternion()
anchor=Matrix.LocRotScale(Vector((.9,.02,.1)),rotation,Vector((.8,.8,.8)))
cut=SimpleNamespace(version=19,frames=2,matrices=[[x for row in anchor.transposed() for x in row]])
record={'animation':Track(),'matrix_index':0}
samples=rigid_samples(cut,record)
expected=C@anchor@CI
assert max(abs(a-b) for ar,br in zip(samples[0],expected) for a,b in zip(ar,br))<1e-6
assert max(abs(x-.8) for x in samples[1].to_scale())<1e-6,'Scale must not become .64'
assert abs(samples[1].translation.x-1.1)<1e-6,'Anchor-relative translation must not rotate twice'
for version in (18,30):
    cut.version=version
    try:rigid_samples(cut,record)
    except FormatError:pass
    else:raise AssertionError('Unknown rigid convention accepted')
cut.version=19
record['animation'].rows=[[0,0,0,.3,-.2,.1,1,1,1]]*2
try:rigid_samples(cut,record)
except FormatError:pass
else:raise AssertionError('Mismatched source scale accepted')
print('RIGID_ANCHOR_REGRESSION_PASSED')
