"""List or grow CU3 actor / object names without editing source files.

Examples:
  python cu3_name_editor.py list scene.CU3
  python cu3_name_editor.py rename scene.CU3 --actor OLD=NEW --output scene_edited.CU3
  python cu3_name_editor.py rename scene.CU3 --object-index 0=LONG_NAME --output scene_edited.CU3
"""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parent.parent
# Bypass the Blender UI __init__; these reader/editor modules need only stdlib.
package='io_scene_lego_cu3'
module=types.ModuleType(package)
module.__path__=[str(root/'Addon'/package)]
sys.modules[package]=module
from io_scene_lego_cu3.cu3 import Cutscene,FormatError
from io_scene_lego_cu3.name_editor import inventory,rewrite_names,plan_character_replacement


def mapping(values,items,indexed=False):
    out={}
    for value in values:
        if '=' not in value:raise FormatError('Rename arguments must use OLD=NEW or INDEX=NEW')
        key,name=value.split('=',1)
        matches=[i['index'] for i in items if str(i['index'])==key] if indexed else [i['index'] for i in items if i['name']==key]
        if len(matches)!=1:raise FormatError(f'{key!r} matches {len(matches)} entries; use a unique name or the index option')
        if matches[0] in out:raise FormatError('Duplicate rename target')
        out[matches[0]]=name
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=parser.add_subparsers(dest='command',required=True)
    listing=sub.add_parser('list');listing.add_argument('input',type=Path)
    rename=sub.add_parser('rename');rename.add_argument('input',type=Path);rename.add_argument('--output',type=Path,required=True)
    for option in ('actor','object','actor-index','object-index','record'):rename.add_argument('--'+option,action='append',default=[])
    rename.add_argument('--character',action='append',default=[],help='Replace every root instance: CHARACTER=REPLACEMENT, without Instance prefixes')
    rename.add_argument('--character-scope',choices=['character','shared-reference'],default='character')
    rename.add_argument('--force',action='store_true',help='Allow replacing an existing output copy; input is always protected')
    args=parser.parse_args();cut=Cutscene(args.input);entries=inventory(cut)
    if args.command=='list':print(json.dumps(entries,indent=2));return
    if args.output.resolve()==args.input.resolve():raise FormatError('Input and output must be different files')
    if args.output.exists() and not args.force:raise FormatError('Output already exists; choose a new filename or explicitly use --force')
    report_path=args.output.with_suffix(args.output.suffix+'.rename.json')
    if report_path.exists() and not args.force:raise FormatError('Output manifest already exists; choose a new filename or explicitly use --force')
    actors=mapping(args.actor,entries['actors']);objects=mapping(args.object,entries['objects'])
    for target,values,items in ((actors,args.actor_index,entries['actors']),(objects,args.object_index,entries['objects'])):
        extra=mapping(values,items,indexed=True)
        if set(extra)&set(target):raise FormatError('Duplicate rename target')
        target.update(extra)
    records={}
    plans=[]
    for value in args.character:
        if '=' not in value:raise FormatError('Character replacement requires OLD=NEW')
        old,new=value.split('=',1);extra,plan=plan_character_replacement(cut,old,new,args.character_scope)
        if set(extra)&set(actors):raise FormatError('Character plan overlaps another actor edit')
        actors.update(extra);plans.append(plan)
    if plans:
        final_names=[actors.get(a['index'],a['name']).casefold() for a in cut.actors if a['parent'] is None]
        if len(set(final_names))!=len(final_names):
            raise FormatError('Combined character plans create duplicate root instance names; choose distinct explicit instance names')
    for value in args.record:
        key,name=value.split('=',1);ai,ri=map(int,key.split(':'))
        if (ai,ri) in records:raise FormatError('Duplicate record rename target')
        records[ai,ri]=name
    if not (actors or objects or records):raise FormatError('No rename requested')
    data,report=rewrite_names(cut,actors,objects,records)
    report['character_plans']=plans
    # Exclusive creation prevents an accidental race from replacing another file.
    with args.output.open('wb' if args.force else 'xb') as stream:stream.write(data)
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output.resolve()),report=str(report_path.resolve()),**report),indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as exc:print('ERROR:',exc,file=sys.stderr);sys.exit(2)
