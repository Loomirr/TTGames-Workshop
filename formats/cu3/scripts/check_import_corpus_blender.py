"""Run the actual reference-import operator on user-selected CU3 folders.

This checks inspection/import dispatch, not complete meshes or game fidelity.
Reports are written only to the explicitly selected new output file.
"""
import argparse,json,sys,traceback
from pathlib import Path
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Addon'))
import io_scene_lego_cu3 as addon
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('inputs',nargs='+',type=Path)
parser.add_argument('--report',required=True,type=Path)
parser.add_argument('--limit',type=int,default=0)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.report.exists():raise SystemExit('Choose a new report filename')
files=sorted({p.resolve() for source in args.inputs for p in ([source] if source.is_file() else source.rglob('*'))
              if p.is_file() and p.suffix.lower()=='.cu3'})
if args.limit:files=files[:args.limit]
if not files:raise SystemExit('No CU3 inputs found')
addon.register();rows=[];original=bpy.context.scene
stores=('scenes','objects','collections','texts','actions','meshes','armatures','node_groups')
try:
    for path in files:
        before={name:set(getattr(bpy.data,name)) for name in stores}
        scene=bpy.data.scenes.new('CU3 import regression');bpy.context.window.scene=scene
        row={'file':str(path)}
        try:
            assert bpy.ops.import_scene.lego_cu3(filepath=str(path),mode='INSPECT')=={'FINISHED'}
            text=next(t for t in bpy.data.texts if t not in before['texts'])
            report=json.loads(text.as_string())
            assert len(scene.objects)==len(report['actors'])
            row.update(status='inspected',version=report['version'],actors=len(report['actors']),frames=report['frames'])
        except Exception as error:
            row.update(status='rejected',error=str(error))
        finally:
            bpy.context.window.scene=original
            created={item for name in stores for item in getattr(bpy.data,name) if item not in before[name]}
            bpy.data.batch_remove(ids=created)
        rows.append(row)
    result={'blender':bpy.app.version_string,'mode':'INSPECT','files':len(rows),
            'inspected':sum(r['status']=='inspected' for r in rows),'rejected':sum(r['status']=='rejected' for r in rows),'results':rows}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print('IMPORT_CORPUS_COMPLETE',json.dumps({k:v for k,v in result.items() if k!='results'}),flush=True)
finally:addon.unregister()
