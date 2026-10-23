"""Original-file regression for reversible Clone hand display translations.

Blender background arguments: original Chars folder, Clone Idle.ani, new output.
Checks source preservation, opt-out, mesh-only parity and other-rig exclusion.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('characters', type=Path)
    parser.add_argument('idle', type=Path)
    parser.add_argument('output', type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True,exist_ok=False)
    component=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('lsw1_hand_check',component/'__init__.py',submodule_search_locations=[str(component)])
    addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon)
    from lsw1_hand_check.hgp import HGP
    from lsw1_hand_check.importer import import_character, matrix, C
    from lsw1_hand_check.preview_pose import translation_offsets
    sys.path.insert(0,str(component/'tools'))
    from animation_records import AnimationRecords
    clip=AnimationRecords(args.idle.read_bytes(),'ANI')
    assert clip.sha256=='54baa9ecb5d5988b50a8eef0a1e5caaa05dea72fea1ce6a3cb2f995053443689'
    expected_names={'Clone.hgp','Clone_Ep3.hgp','Clone_Ep3_Pilot.hgp','Clone_Ep3_Swamp.hgp','Clone_Ep3_Walker.hgp','stormTrooper.hgp'}
    selected=[];census=0
    for path in args.characters.rglob('*'):
        if path.suffix.lower()!='.hgp':continue
        h=HGP(path);census+=1
        if translation_offsets(h.bones):selected.append(path)
    assert {p.name for p in selected}==expected_names and len(selected)==6
    reports=[]
    for path in selected:
        h=HGP(path)
        # A renamed bone, changed parent, local bind or inverse bind must refuse
        # the known preview profile, even with unchanged filename/bone count.
        for key in ('name','parent','local','inverse'):
            changed=copy.deepcopy(h.bones)
            if key=='name':changed[7][key]+='_edited'
            elif key=='parent':changed[7][key]=5
            else:
                values=list(changed[7][key]);values[12]+=.001;changed[7][key]=values
            assert translation_offsets(changed)=={}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        raw=import_character(bpy.context,path,textures=False,correct_preview_pose=False)
        posed=import_character(bpy.context,path,textures=False,correct_preview_pose=True)
        baked=import_character(bpy.context,path,textures=False,armature=False,correct_preview_pose=True)
        bpy.context.view_layer.update()
        assert not raw.get('lsw1_preview_pose_correction') and posed.get('lsw1_preview_pose_correction')
        assert all(a.matrix_local==b.matrix_local for a,b in zip(raw.data.bones,posed.data.bones))
        expected_offsets={}
        for name,track in (('leftElbow|leftHand',7),('rightElbow|rightHand',11)):
            records=clip.records[track*9:track*9+3]
            assert all(r['kind']==0 for r in records)
            target=Vector((records[0]['value'],-records[2]['value'],records[1]['value']))
            local=C@matrix(h.bones[track]['local'])@C
            delta=target-local.translation
            parent=raw.data.bones[name].parent
            expected_offsets[name]=parent.matrix_local.to_3x3()@delta
        maximum=0.;moved=0
        raw_objects=[o for o in raw.children if o.type=='MESH']
        posed_objects=[o for o in posed.children if o.type=='MESH']
        baked_objects=[o for o in baked.children if o.type=='MESH']
        assert len(raw_objects)==len(posed_objects)==len(baked_objects)
        for original,candidate,static in zip(raw_objects,posed_objects,baked_objects):
            assert [tuple(v.co) for v in original.data.vertices]==[tuple(v.co) for v in candidate.data.vertices]
            assert [tuple(p.vertices) for p in original.data.polygons]==[tuple(p.vertices) for p in candidate.data.polygons]
            evaluated=candidate.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            for v,pv,bv in zip(original.data.vertices,evaluated.vertices,static.data.vertices):
                expected=v.co.copy()
                for group in v.groups:
                    name=original.vertex_groups[group.group].name
                    expected+=expected_offsets.get(name,Vector())*group.weight
                error=max((pv.co-expected).length,(bv.co-expected).length)
                assert error<2e-6,(path.name,v.index,error)
                maximum=max(maximum,error)
                moved+=int((expected-v.co).length>1e-5)
            candidate.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
        assert moved>=200
        reports.append(dict(model=path.name,moved_vertices=moved,maximum_error=maximum))
    (args.output/'report.json').write_text(json.dumps(dict(census=census,corrected=len(selected),models=reports),indent=2))
    print('HAND_PREVIEW_PASS',census,'rigs checked;',len(selected),'corrected; source data and mesh-only parity verified')


if __name__=='__main__':main()
