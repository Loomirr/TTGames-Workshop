"""Experimental active native AN4 action export to a separate loose file."""
import hashlib
import json
from pathlib import Path
from mathutils import Matrix, Euler
from ._core.cu3 import FormatError
from ._core.an4 import AnimationFile
from ._core.an4_edit import patch_record
from ._core.animation_bank import AnimationBank
from ._core.animation_details import detail_tracks,model_detail_skeletons
from ._core.blender_import import C,CI,row_matrix,check_rig,rotations


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


def bone_fingerprints(action,rig):
    """Remember untouched native channels so a local edit needn't rebake them."""
    rows={bone.name:[] for bone in rig.pose.bones}
    prefixes={bone.name:bone.path_from_id()+'.' for bone in rig.pose.bones}
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for name,prefix in prefixes.items():
                        if curve.data_path.startswith(prefix):
                            rows[name].append((bag.slot_handle,curve.data_path,curve.array_index,
                                [(tuple(k.co),k.interpolation,tuple(k.handle_left),tuple(k.handle_right)) for k in curve.keyframe_points]))
                            break
    return {name:hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest() for name,value in rows.items()}


def check_linked_actions(action):
    """Native bundle/body writers do not serialize edited companion actions."""
    import bpy
    for field in ('tt_attachment_actions', 'tt_facial_actions'):
        for track in json.loads(action.get(field, '[]')):
            expected = track.get('fingerprint')
            if not expected:continue  # Older imported clips lack this baseline.
            companion = bpy.data.actions.get(track['action'])
            if companion is None or action_fingerprint(companion) != expected:
                raise FormatError('Linked attachment/facial action has edits; native companion animation writing is unsupported: '+track['action'])


def native_worlds(anim,skeleton,rows,*,rotation_values=None):
    worlds=[];scales=[];flip=Matrix.Diagonal((1,1,-1,1))
    for joint,channels in zip(skeleton['joints'],rows):
        index=joint['index'];flags=anim.node_flags[index]
        local=(rotation_values[index].to_matrix().to_4x4() if rotation_values is not None else
               Euler((-channels[3],-channels[4],channels[5]),'XYZ').to_matrix().to_4x4())
        if flags&0x20:
            orient=flip@row_matrix(joint['orient_row_major'])@flip;orient.translation=(0,0,0)
            local=orient@local
        parent_scale=scales[joint['parent']] if joint['parent'] is not None else (1,1,1)
        scale=channels[6:9] if anim.curves==9 and flags&8 else (1,1,1)
        local=local@Matrix.Diagonal((*scale,1))
        if flags&0x10:
            if any(abs(v)<=1e-8 for v in parent_scale):raise FormatError('Native animation has a degenerate parent scale')
            local=Matrix.Diagonal((*[1/v for v in parent_scale],1))@local
        local.translation=(channels[0],channels[1],-channels[2])
        local=C@local@CI
        worlds.append(worlds[joint['parent']]@local if joint['parent'] is not None else local)
        cumulative=tuple(scale) if flags&0x10 else tuple(a*b for a,b in zip(parent_scale,scale))
        scales.append((1,1,1) if joint['parent'] is None and flags&0x40 else cumulative)
    return worlds,scales


def sample_native_pose(context,rig,skeleton,anim,*,changed_bones=None,base_skeleton=None,base_animation=None,base_samples=None):
    """Apply authored Blender-basis deltas to exact native source transforms.

    Blender's TRS keys cannot store all source basis shear. Using the native
    reference avoids baking that import approximation back into untouched bones.
    Reduced rigs apply the same world-space change to their own native pose.
    """
    anim.prepare(scene_channels=True)
    samples=[];previous={};flip=Matrix.Diagonal((1,1,-1,1))
    base_names={item['name']:item for item in base_skeleton['joints']} if base_skeleton else None
    for frame in range(1,anim.frames+1):
        context.scene.frame_set(frame);rows=[]
        original=anim.sample(frame-1)
        old_worlds,_=native_worlds(anim,skeleton,original)
        reference_worlds,_=native_worlds(anim,skeleton,original,rotation_values=rotations(anim,frame-1))
        if base_skeleton:
            base_old,_=native_worlds(base_animation,base_skeleton,base_animation.sample(frame-1))
            base_new,_=native_worlds(base_animation,base_skeleton,base_samples[frame-1])
        for joint in skeleton['joints']:
            index=joint['index'];chain={joint['name']}
            if base_skeleton:
                stop=skeleton['joints'][joint['parent']]['name'] if joint['parent'] is not None else None
                ancestor=base_names[joint['name']]['parent']
                while ancestor is not None and base_skeleton['joints'][ancestor]['name']!=stop:
                    chain.add(base_skeleton['joints'][ancestor]['name'])
                    ancestor=base_skeleton['joints'][ancestor]['parent']
            flags=anim.node_flags[index]
            if changed_bones is not None and not chain.intersection(changed_bones):
                channels=list(original[index])
                if anim.curves==9 and not flags&8:channels[6:9]=(1,1,1)
                rows.append(channels)
                continue
            emitted,scales=native_worlds(anim,dict(joints=skeleton['joints'][:index]),rows)
            parent_world=emitted[joint['parent']] if joint['parent'] is not None else None
            parent_scale=scales[joint['parent']] if joint['parent'] is not None else (1,1,1)
            if base_skeleton:
                base_index=base_names[joint['name']]['index']
                desired=base_new[base_index]@base_old[base_index].inverted()@old_worlds[index]
            else:
                bone=rig.data.bones[joint['name']]
                old_parent=reference_worlds[joint['parent']] if joint['parent'] is not None else None
                kwargs=dict(parent_matrix=old_parent,parent_matrix_local=bone.parent.matrix_local) if bone.parent else {}
                exact_basis=bone.convert_local_to_pose(reference_worlds[index],bone.matrix_local,invert=True,**kwargs)
                representable=Matrix.LocRotScale(*exact_basis.decompose())
                authored=exact_basis@representable.inverted()@rig.pose.bones[joint['name']].matrix_basis
                kwargs=dict(parent_matrix=parent_world,parent_matrix_local=bone.parent.matrix_local) if bone.parent else {}
                desired=bone.convert_local_to_pose(authored,bone.matrix_local,**kwargs)
            local=parent_world.inverted()@desired if parent_world is not None else desired
            local=CI@local@C;translation=local.translation.copy()
            rotation=local.to_3x3().to_4x4();rotation.translation=(0,0,0)
            if flags&0x10:rotation=Matrix.Diagonal((*parent_scale,1))@rotation
            if flags&0x20:
                orient=flip@row_matrix(joint['orient_row_major'])@flip;orient.translation=(0,0,0)
                rotation=orient.inverted()@rotation
            _,quaternion,scale=rotation.decompose()
            if any(v<=1e-8 for v in scale):raise FormatError('Native AN4 export requires positive nonzero scales')
            recovered=quaternion.to_matrix().to_4x4()@Matrix.Diagonal((*scale,1))
            if max(abs(rotation[i][j]-recovered[i][j]) for i in range(3) for j in range(3))>1e-4:
                raise FormatError(f'Native AN4 export cannot encode shear/reflection: {joint["name"]}, frame {frame}')
            if anim.curves==6 and any(abs(v-1)>1e-4 for v in scale):
                raise FormatError('Six-channel ANI-D cannot encode bone scale; use an existing nine-channel source')
            rotation=quaternion.to_matrix().to_4x4()
            angles=rotation.to_euler('XYZ',previous[index]) if index in previous else rotation.to_euler('XYZ')
            previous[index]=angles.copy()
            rows.append([translation.x,translation.y,-translation.z,-angles.x,-angles.y,angles.z]+(list(scale) if anim.curves==9 else []))
        samples.append(rows)
    return samples


def export_action(context,rig,destination,*,omit_auxiliary=False,rebuild_bank=False):
    destination=Path(destination).expanduser().resolve()
    suffix='.PAK' if rebuild_bank else '.AN4'
    report_path=destination.with_suffix(suffix+'.json')
    if destination.suffix.casefold()!=suffix.lower() or destination.exists() or report_path.exists():
        raise FormatError('Choose a new '+suffix+' output file')
    roots=[Path(rig['tt_character_assets_root']).resolve()]
    if rig.get('tt_character_cache'):roots.append(Path(rig['tt_character_cache']).resolve())
    if any(destination.is_relative_to(root) for root in roots):raise FormatError('Export outside the installed game and cache/source tree')
    if rig.constraints or any(b.constraints for b in rig.pose.bones):raise FormatError('This rig has constraints. Bake their visible motion to pose keyframes on a copy of the imported rig, then remove the constraints. Keep its original bones and rest pose; see the animation export guide')
    if rig.animation_data and any(not track.mute for track in rig.animation_data.nla_tracks):raise FormatError('Mute NLA tracks before active-action export')
    action=rig.animation_data.action if rig.animation_data else None
    if not action or not action.get('tt_native_pose_fingerprint'):raise FormatError('Select a newly imported native AN4 clip')
    check_linked_actions(action)
    skeleton=json.loads(rig['tt_character_skeleton']);check_rig(rig,skeleton)
    bank=None
    if action.get('tt_authored_action'):
        entry=json.loads(action['tt_authored_action']);source_path=Path(entry['source'])
        if entry['member']:
            bank=AnimationBank(source_path)
            data=bank.read(entry['member'])
            stored=bank.read_stored(entry['member'])
        else:
            data=stored=source_path.read_bytes()
    else:
        source_path=Path(action['tt_native_animation_source']);data=stored=source_path.read_bytes()
    if rebuild_bank:
        if bank is None:raise FormatError('This clip was not imported from an animation bank')
        bank_hash=action.get('tt_animation_bank_sha256')
        if not bank_hash:raise FormatError('Reimport this clip to record its source bank before PAK export')
        if hashlib.sha256(bank.data).hexdigest()!=bank_hash:raise FormatError('Animation bank changed since import')
    if destination.is_relative_to(source_path.parent):raise FormatError('Choose a separate output folder')
    if hashlib.sha256(data).hexdigest()!=action['cu3_sha256']:raise FormatError('Native AN4 source changed since import')
    source=AnimationFile(source_path,data=stored)
    actor=[a for a in source.actors if a['name']==action['cu3_actor']]
    if len(actor)!=1:raise FormatError('Exact native AN4 actor is no longer available')
    record_index=action['cu3_record'];anim=actor[0]['records'][record_index]['animation']
    if anim.curves not in (6,9):raise FormatError('The AN4 writer currently requires six/nine-channel source records')
    if action_fingerprint(action)==action['tt_native_pose_fingerprint']:
        output=stored;report=dict(schema='tt.ani-d-sample-edit.v2',changed=False,source_sha256=source.sha256,
            output_sha256=source.sha256,validation='Unchanged action: original standalone/member bytes preserved',
            storage=dict(source='Deflate_v1.0' if stored.startswith(b'Deflate_v1.0') else 'raw',
                         output='Deflate_v1.0' if stored.startswith(b'Deflate_v1.0') else 'raw',
                         decoded_bytes=len(source.data),stored_bytes=len(stored)),
            limitations=['PAK members are exported as separate AN4 files; their source bank is unchanged.'])
    else:
        if (action.frame_start,action.frame_end)!=(1,anim.frames):raise FormatError('Preserve the original clip frame range')
        previous_frame=context.scene.frame_current;previous_subframe=context.scene.frame_subframe
        tracks=[anim] if omit_auxiliary else detail_tracks(anim)
        variants=model_detail_skeletons(skeleton) if any(t.at!=anim.at for t in tracks) else [skeleton]*len(tracks)
        if len(variants)!=len(tracks):raise FormatError('Animation and model detail slot counts disagree')
        for variant,track in zip(variants,tracks):
            if len(variant['joints'])!=track.nodes:
                raise FormatError('Animation detail slot does not match its native skeleton')
            # A zero-offset alias must actually have the base hierarchy/rest pose.
            if track.at==anim.at and variant is not skeleton:
                for left,right in zip(variant['joints'],skeleton['joints']):
                    if any(left[field]!=right[field] for field in ('name','parent','orient_row_major','inverse_world_bind_row_major')):
                        raise FormatError('Aliased animation detail has a different native rig')
        detail_rows={}
        baseline=json.loads(action.get('tt_native_bone_fingerprints','{}'))
        current=bone_fingerprints(action,rig)
        changed_bones={name for name,value in current.items() if baseline.get(name)!=value}
        try:
            samples=sample_native_pose(context,rig,skeleton,anim,changed_bones=changed_bones)
            for index,(variant,track) in enumerate(zip(variants,tracks)):
                if track.at!=anim.at:
                    detail_rows[index]=sample_native_pose(context,rig,variant,track,
                        changed_bones=changed_bones,base_skeleton=skeleton,base_animation=anim,base_samples=samples)
        finally:context.scene.frame_set(previous_frame,subframe=previous_subframe)
        output,report=patch_record(stored,action['cu3_actor'],record_index,samples,source.sha256,
            omit_auxiliary=omit_auxiliary,detail_samples=detail_rows);report['changed']=True
    report['imported_source_sha256']=action['cu3_sha256']
    report['source']=source_path.name
    if rebuild_bank:
        output=bank.replace_members({entry['member']:output},bank_hash)
        report['bank']=dict(source_sha256=bank_hash,output_sha256=hashlib.sha256(output).hexdigest(),
            member=entry['member'],member_count=len(bank.entries),other_members_unchanged=True,
            layout='ordered, 4-byte aligned, 2-byte minimum zero padding',
            validation='All stored members checked; game validation is specific to the tested clip and game')
        report['limitations']=[note for note in report.get('limitations',[]) if not note.startswith('PAK members are exported')]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:stream.write(output)
    with report_path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    return report
