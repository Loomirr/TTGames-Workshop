"""List cutscene character companions before opening Blender; no assets modified."""
import argparse
import json
import sys
import types
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('tt_dependency_check');package.__path__=[str(source)];sys.modules[package.__name__]=package
from tt_dependency_check.asset_index import AssetIndex
from tt_dependency_check.cu3 import Cutscene
from tt_dependency_check.dependencies import ResourceResolver, dependency_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cutscene',type=Path)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--game',choices=('LB3','LMSH1'),required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report filename')
    result=dependency_report(Cutscene(args.cutscene),ResourceResolver(AssetIndex(args.assets),args.game))
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('resources','source')},indent=2))

if __name__=='__main__':main()
