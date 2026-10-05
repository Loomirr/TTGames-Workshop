"""Experimental active native AN4 action export to a separate loose file."""
import hashlib
import json
from pathlib import Path
from mathutils import Matrix
from ._core.cu3 import FormatError
from ._core.an4 import AnimationFile
from ._core.an4_edit import patch_record
from ._core.animation_bank import AnimationBank
from ._core.blender_import import C,CI,row_matrix,check_rig


def action_fingerprint(action):
    rows=[]
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.modifiers:raise FormatError('Bake action modifiers before native export')
                    rows.append((bag.slot_handle,curve.data_path,curve.array_index,
                        [(tuple(k.co),k.interpolation,tuple(k.handle_left),tuple(k.handle_right)) for k in curve.keyframe_points]))
    payload=dict(curves=rows,frame_range=[action.use_frame_range,action.frame_start,action.frame_end])
    return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()


def export_action(context,rig,destination,*,omit_auxiliary=False):
    destination=Path(destination).expanduser().resolve()
    if destination.suffix.casefold()!='.an4' or destination.exists() or destination.with_suffix('.AN4.json').exists():
        raise FormatError('Choose a new .AN4 output file')
    roots=[Path(rig['tt_character_assets_root']).resolve()]
    if rig.get('tt_character_cache'):roots.append(Path(rig['tt_character_cache']).resolve())
    if any(destination.is_relative_to(root) for root in roots):raise FormatError('Export outside the installed game and cache/source tree')
    if rig.constraints or any(b.constraints for b in rig.pose.bones):raise FormatError('Bake constraints to a clean native rig before AN4 export')
    if rig.animation_data and any(not track.mute for track in rig.animation_data.nla_tracks):raise FormatError('Mute NLA tracks before active-action export')
    action=rig.animation_data.action if rig.animation_data else None
    if not action or not action.get('tt_native_pose_fingerprint'):raise FormatError('Select a newly imported native AN4 clip')
    skeleton=json.loads(rig['tt_character_skeleton']);check_rig(rig,skeleton)
    if action.get('tt_authored_action'):
        entry=json.loads(action['tt_authored_action']);source_path=Path(entry['source'])
        data=AnimationBank(source_path).read(entry['member']) if entry['member'] else source_path.read_bytes()
    else:
        source_path=Path(action['tt_native_animation_source']);data=source_path.read_bytes()
    if destination.is_relative_to(source_path.parent):raise FormatError('Choose a separate output folder')
    if hashlib.sha256(data).hexdigest()!=action['cu3_sha256']:raise FormatError('Native AN4 source changed since import')
    source=AnimationFile(source_path,data=data)
    actor=[a for a in source.actors if a['name']==action['cu3_actor']]
    if len(actor)!=1:raise FormatError('Exact native AN4 actor is no longer available')
    record_index=action['cu3_record'];anim=actor[0]['records'][record_index]['animation']
    if anim.curves not in (6,9):raise FormatError('The ANI-D writer currently requires six/nine-channel source records')
    if action_fingerprint(action)==action['tt_native_pose_fingerprint']:
        output=data;report=dict(schema='tt.ani-d-sample-edit.v1',changed=False,source_sha256=source.sha256,
            output_sha256=source.sha256,validation='Unchanged action: original standalone/member bytes preserved',
            limitations=['PAK members are exported as separate AN4 files; their source bank is unchanged.'])
    else:
        if (action.frame_start,action.frame_end)!=(1,anim.frames):raise FormatError('Preserve the original clip frame range')
        previous_frame=context.scene.frame_current;previous_subframe=context.scene.frame_subframe
        samples=[];previous={};flip=Matrix.Diagonal((1,1,-1,1))
        try:
            for frame in range(1,anim.frames+1):
                context.scene.frame_set(frame);rows=[]
                cumulative_scales=[]
                for joint in skeleton['joints']:
                    bone=rig.pose.bones[joint['name']];local=bone.parent.matrix.inverted() @ bone.matrix if bone.parent else bone.matrix.copy()
                    local=CI @ local @ C;translation=local.translation.copy()
                    rotation=local.to_3x3().to_4x4();rotation.translation=(0,0,0)
                    flags=anim.node_flags[joint['index']]
                    parent_scale=cumulative_scales[joint['parent']] if joint['parent'] is not None else (1,1,1)
                    if flags & 0x10:
                        rotation=Matrix.Diagonal((*parent_scale,1)) @ rotation
                    if flags & 0x20:
                        orient=flip @ row_matrix(joint['orient_row_major']) @ flip;orient.translation=(0,0,0)
                        rotation=orient.inverted() @ rotation
                    _,quaternion,scale=rotation.decompose()
                    if any(v<=1e-8 for v in scale):raise FormatError('Native AN4 export requires positive nonzero scales')
                    recovered=quaternion.to_matrix().to_4x4() @ Matrix.Diagonal((*scale,1))
                    if max(abs(rotation[i][j]-recovered[i][j]) for i in range(3) for j in range(3))>1e-4:
                        raise FormatError(f'Native AN4 export cannot encode shear/reflection: {joint["name"]}, frame {frame}')
                    if anim.curves==6 and any(abs(v-1)>1e-4 for v in scale):
                        raise FormatError('Six-channel ANI-D cannot encode bone scale; use an existing nine-channel source')
                    cumulative=tuple(a*b for a,b in zip(parent_scale,scale))
                    if flags & 0x10:cumulative=tuple(scale)
                    cumulative_scales.append((1,1,1) if joint['parent'] is None and flags & 0x40 else cumulative)
                    rotation=quaternion.to_matrix().to_4x4()
                    angles=rotation.to_euler('XYZ',previous.get(joint['index'])) if joint['index'] in previous else rotation.to_euler('XYZ')
                    previous[joint['index']]=angles.copy()
                    rows.append([translation.x,translation.y,-translation.z,-angles.x,-angles.y,angles.z]+(list(scale) if anim.curves==9 else []))
                samples.append(rows)
        finally:context.scene.frame_set(previous_frame,subframe=previous_subframe)
        output,report=patch_record(data,action['cu3_actor'],record_index,samples,action['cu3_sha256'],omit_auxiliary=omit_auxiliary);report['changed']=True
    report['source']=source_path.name
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:stream.write(output)
    destination.with_suffix('.AN4.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
