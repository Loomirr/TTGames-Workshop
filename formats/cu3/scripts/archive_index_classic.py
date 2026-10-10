"""List supported PC DAT index layouts; never alter or extract an archive."""
import argparse
import json
from pathlib import Path
import sys
import types

addon=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
if 'tt_dependency_check' not in sys.modules:
    package=types.ModuleType('tt_dependency_check');package.__path__=[str(addon)]
    sys.modules[package.__name__]=package
from tt_dependency_check.archive_v5 import index_v5
from tt_dependency_check.archive_assets import index_v6

LAYOUTS={'LB1':-2,'TCS':-3,'LB2':-4,'SW3':-4,'LMSH1':-5,'HOBBIT':-5,'MOVIE1':-5,'LB3':-6}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--game',choices=LAYOUTS,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Choose a new report filename')
    try:
        reader=index_v6 if args.game in ('HOBBIT','MOVIE1','LB3') else index_v5
        options={'version_expected':LAYOUTS[args.game]} if reader is index_v6 else {'layout':LAYOUTS[args.game]}
        entries=reader(args.source,**options)
        report=dict(game=args.game,layout=LAYOUTS[args.game],entries=entries,
                    scope='Validated paths and file spans; no model, animation or payload fidelity claim')
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2);stream.write('\n')
    except (OSError,ValueError) as error:
        parser.error(str(error))
    print(f'{len(entries)} entries indexed; archive unchanged')


if __name__=='__main__':main()
