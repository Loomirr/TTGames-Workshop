"""Sample compressed Euler endpoints, then shortest-hemisphere normalized lerp.

The game's rotation player constructs two quaternions before interpolation.
0x5c8993-0x5c8a1f chooses hemisphere by dot product, linearly blends,
then normalizes. Translational scalar sampling is deliberately unchanged.
Requires Blender's mathutils; never launches or modifies the game.
"""
import math
import os
from pathlib import Path
from mathutils import Euler, Quaternion
from decode_an4 import animation

def corrected_rotations(clip):
    source=clip['source']
    if os.name == 'nt' and Path(source).is_absolute() and not source.startswith('\\\\?\\'):
        source='\\\\?\\'+source
    decoded, blob, descriptors, offsets, sample = animation(Path(source), debug=True,
        clip_index=clip.get('clip_index',0),actor_name=clip.get('actor'))
    assert decoded['sha256'] == clip['sha256']
    assert decoded['format_flags'] & 0x80, 'Explicit key timing required'
    result=[]
    for frame in range(clip['frame_count']):
        source_frame=frame+clip.get('sample_frame_offset',0)
        pos=max(0,min(clip['key_count']-1,(source_frame-clip['first_frame'])*clip['compression_ratio']))
        whole=int(pos); fraction=pos-whole
        before=sample(frame,key_position=whole)
        after=sample(frame,key_position=min(whole+1,clip['key_count']-1))
        row=[]
        for node,(a,b) in enumerate(zip(before,after)):
            # Preserve channels marked as held by the format.
            for axis in range(3,6):
                if descriptors[node*6+axis]['step']: b[axis]=a[axis]
            qa=Euler((-a[3],-a[4],a[5]),'XYZ').to_quaternion()
            qb=Euler((-b[3],-b[4],b[5]),'XYZ').to_quaternion()
            if qa.dot(qb)<0: qb.negate()
            q=Quaternion(tuple(x+(y-x)*fraction for x,y in zip(qa,qb)))
            q.normalize()
            assert all(math.isfinite(v) for v in q)
            row.append(q)
        result.append(row)
    return result
