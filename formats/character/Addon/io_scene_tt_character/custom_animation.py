"""Custom body clips retain a native template and an explicit game route."""
import json
from pathlib import Path
import bpy
from ._core.cu3 import FormatError
from ._core.an4 import AnimationFile
from ._core.animation_bank import AnimationBank
from ._core.blender_import import check_rig


def create_custom_clip(rig, name):
    original=rig.animation_data.action if rig.animation_data else None
    if not original or not original.get('tt_native_pose_fingerprint'):
        raise FormatError('Load a native clip to use as the custom animation template')
    check_rig(rig,json.loads(rig['tt_character_skeleton']))
    if not name.strip():raise FormatError('Give the custom clip a name')
    slot=rig.animation_data.action_slot
    if slot is None:raise FormatError('The template has no active action slot')
    previous=next((item for item in rig.tt_clips if item.action==original),None)
    if previous is None:raise FormatError('Select a loaded clip before creating a custom copy')
    copied=original.copy()
    copied.name=name.strip()
    copied.use_fake_user=True
    copied['tt_custom_animation']=True
    copied['tt_custom_template']=original.name
    copied_slot=next((candidate for candidate in copied.slots if candidate.identifier==slot.identifier),None)
    if copied_slot is None:
        bpy.data.actions.remove(copied)
        raise FormatError('Copied action did not retain its native slot')
    item=rig.tt_clips.add()
    item.name,item.action,item.slot=copied.name,copied,copied_slot.identifier
    item.frames,item.fps=previous.frames,previous.fps
    rig.tt_clip_index=len(rig.tt_clips)-1
    return copied


def load_custom_clip(context,rig,path,entry):
    """Preview an external AN4 or matching bank member on a declared route."""
    from .importer import import_catalog_entry
    path=Path(path).expanduser().resolve()
    custom=dict(entry)
    if path.suffix.lower()=='.pak':
        if not entry.get('member'):
            raise FormatError('Select a declared bank animation before loading a custom PAK')
        bank=AnimationBank(path)
        source=AnimationFile(path,data=bank.read_stored(entry['member']))
    elif path.suffix.lower()=='.an4':
        source=AnimationFile(path)
        custom['member']=''
    else:raise FormatError('Choose an AN4 clip or PAK animation bank')
    matches=[record for actor in source.actors if actor['name']==entry['actor']
             for record in actor['records'] if record['name']==entry['clip']]
    if len(matches)!=1:
        raise FormatError('Custom file must retain the selected native actor and clip name')
    custom['source']=str(path)
    report=import_catalog_entry(context,rig,custom)
    if report['imported']:
        action=rig.tt_clips[rig.tt_clip_index].action
        action['tt_custom_animation']=True
        action['tt_custom_route']=json.dumps(entry)
    return report
