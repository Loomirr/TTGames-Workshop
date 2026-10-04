"""Decode original face offsets from an extracted GHG and its extractor log."""
from pathlib import Path
import argparse, hashlib, json, sys, types
ROOT=Path(__file__).resolve().parent.parent
pkg=types.ModuleType('io_scene_lego_cu3');pkg.__path__=[str(ROOT/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from io_scene_lego_cu3.morph import extract_morphs

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('ghg',type=Path)
    ap.add_argument('--log',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    paths=[p.resolve() for p in (args.ghg,args.log,args.output)]
    if paths[2] in paths[:2]:ap.error('Output must be separate from the source model and extractor log')
    raw=args.ghg.read_bytes();result=extract_morphs(raw,args.log.read_text())
    result.update(source=str(args.ghg.resolve()),sha256=hashlib.sha256(raw).hexdigest())
    args.output.write_text(json.dumps(result,separators=(',',':')))
    print(f"Recovered {sum(len(p['targets']) for p in result['parts'].values())} part targets from {len(result['parts'])} mesh parts.")

if __name__=='__main__':main()
