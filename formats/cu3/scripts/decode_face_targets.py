"""Decode original face offsets directly from a supported extracted GHG."""
from pathlib import Path
import argparse, hashlib, json, sys, types
ROOT=Path(__file__).resolve().parent.parent
pkg=types.ModuleType('io_scene_lego_cu3');pkg.__path__=[str(ROOT/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from io_scene_lego_cu3.morph import extract_morphs
from io_scene_lego_cu3.native_mesh import read_mesh_bytes

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('ghg',type=Path)
    ap.add_argument('--log',type=Path,help='Optional legacy plain-text extractor log for cross-checking')
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    inputs=[p.resolve() for p in (args.ghg,args.log) if p is not None]
    if args.output.resolve() in inputs or args.output.exists():ap.error('Choose a new output separate from the source model and optional log')
    raw=args.ghg.read_bytes();model=read_mesh_bytes(raw)
    result=dict(schema='tt.relative-position-targets.v1',mesh_version=model['mesh_version'],
                semantics='Source-space additive vertex offsets; observed BSA ANI-D weights are separate',
                parts={str(p['index']):p['morphs'] for p in model['parts'] if p['morphs']})
    if not result['parts']:ap.error('No supported relative-position targets found in this model')
    if args.log:
        legacy=extract_morphs(raw,args.log.read_text())
        if legacy!=result:ap.error('Legacy extractor log disagrees with native decoded mesh parts')
    result.update(source=str(args.ghg.resolve()),sha256=hashlib.sha256(raw).hexdigest())
    args.output.write_text(json.dumps(result,separators=(',',':')))
    print(f"Recovered {sum(len(p['targets']) for p in result['parts'].values())} part targets from {len(result['parts'])} mesh parts.")

if __name__=='__main__':main()
