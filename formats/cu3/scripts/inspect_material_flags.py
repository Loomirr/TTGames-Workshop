"""Inspect observed UMTL material flags using locally extracted record metadata."""
import argparse,json,struct,sys,hashlib,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Addon'))
package=types.ModuleType('io_scene_lego_cu3');package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')];sys.modules[package.__name__]=package
from io_scene_lego_cu3.material_flags import read_render_flags
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('materials',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
data=args.source.read_bytes();at=data.index(b'LTMU');version=struct.unpack_from('>I',data,at+4)[0]
rows=read_render_flags(data,json.loads(args.materials.read_text()),version)
if args.output.resolve() in (args.source.resolve(),args.materials.resolve()) or args.output.exists():raise ValueError('Choose a new output file; inputs and existing files are protected')
with args.output.open('x') as output:json.dump(dict(source_sha256=hashlib.sha256(data).hexdigest(),version=version,materials=rows),output,indent=2)
print(f'Validated {len(rows)} material render flags (UMTL {version}).')
