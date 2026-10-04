"""Exercise asset-root assembly on unrelated CU3 inputs and report partial results.

Run in Blender background mode. A completed operator is NOT counted as a
complete cutscene. Optional scenes/images are local inspection artifacts.
"""
import argparse
import json
import sys
import time
from pathlib import Path
import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'Addon'))
from io_scene_lego_cu3.cu3 import Cutscene
from io_scene_lego_cu3.scene_assembly import assemble

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('inputs',nargs='+',type=Path)
parser.add_argument('--assets',required=True,type=Path)
parser.add_argument('--game',required=True,choices=('LB3','LMSH1'))
parser.add_argument('--output',required=True,type=Path)
parser.add_argument('--save-scenes',action='store_true')
parser.add_argument('--render-midpoint',action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
args.output = args.output.resolve()
args.assets = args.assets.resolve()
args.inputs = [p.resolve() for p in args.inputs]
if args.output.exists():raise SystemExit('Choose a new output directory')
args.output.mkdir(parents=True)
rows = []
for number,path in enumerate(args.inputs,1):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    started = time.monotonic()
    row = {'file':str(path.resolve()),'game':args.game,'complete':False}
    stem = f'{number:03d}_{path.stem}'
    try:
        cut = Cutscene(path)
        scene, report = assemble(cut,args.assets,args.game,bpy.context)
        meshes = [o for o in scene.objects if o.type=='MESH']
        row.update(status='partial_actor_scene' if meshes else 'no_actor_geometry',
                   source_actor_nodes=len(cut.actors),
                   assembled_actor_nodes=len(cut.actors)-len(report['unassembled_actor_nodes']),
                   model_instances=len(report['actors']),meshes=len(meshes),
                   camera=report.get('camera'),issues=report['issues'],
                   unresolved_materials=report['materials'],
                   unassembled_actor_nodes=report['unassembled_actor_nodes'],
                   limitations=report['limitations'])
        scene.frame_set(max(1,cut.frames//2))
        if args.save_scenes:
            row['blend']=stem+'.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(args.output/row['blend']))
        if args.render_midpoint and meshes and scene.camera:
            scene.render.resolution_x=640
            scene.render.resolution_y=round(640/report['camera']['aspect'])
            scene.render.resolution_percentage=100
            scene.render.filepath=str(args.output/(stem+'.png'))
            try:
                bpy.ops.render.render(write_still=True,scene=scene.name)
                row['preview']={'file':stem+'.png','frame':scene.frame_current,
                                'kind':'Source camera, available actors only; inspection lighting; no environment'}
            except RuntimeError as error:
                row['preview_error']=str(error)
    except Exception as error:
        row.update(status='rejected',error=f'{type(error).__name__}: {error}')
    row['seconds']=round(time.monotonic()-started,2)
    rows.append(row)
    (args.output/'report.json').write_text(json.dumps({'results':rows},indent=2),encoding='utf-8')
    print('ASSEMBLY_SAMPLE',json.dumps({k:v for k,v in row.items() if k in ('file','status','assembled_actor_nodes','source_actor_nodes','model_instances','seconds','error')}),flush=True)
