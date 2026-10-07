"""Inspect a CC40TAD DAT/HDR index without extracting files or accepting unknown tails.

Writes bounded JSON metadata to a new, user-selected report filename. A report
with unknown suffix grammar is useful for research, but does not enable archive
extraction. Exit status is 0 for completely validated known index tables, 2 for
an unsupported/invalid index or an inspection error. Neither status proves that
the archive's compression modes or game assets are supported.
"""
from pathlib import Path
import argparse
import json
import sys
import types

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.archive_cc import diagnose_archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='User-owned DAT archive or detached HDR index to inspect')
    parser.add_argument('report', type=Path, help='New JSON filename; an existing file or link is never replaced')
    args = parser.parse_args(argv)
    if args.report.exists() or args.report.is_symlink():
        parser.error('Choose a new diagnostic report filename')
    try:
        report = diagnose_archive(args.archive)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        # The earlier check provides a clear error; exclusive creation is what
        # prevents replacement if another process creates this name meanwhile.
        with args.report.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Saved diagnostic report: {args.report}")
    print(f"Index status: {report['status']}. No files were extracted.")
    if report['status'] == 'unsupported_suffix':
        layout, suffix = report['layout'], report['suffix']
        print(f"Kind {layout['kind']} / version {layout['version']}; validated tables end at index "
              f"offset 0x{suffix['offset']:x}, with {suffix['bytes']} unverified suffix bytes. "
              'Extraction remains blocked until that grammar is established.')
    elif report['status'] == 'invalid_prefix':
        print(f"Known table validation failed: {report['error']}")
    else:
        print('Known index tables validate completely; this inspection does not test payload codecs or game support.')
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
