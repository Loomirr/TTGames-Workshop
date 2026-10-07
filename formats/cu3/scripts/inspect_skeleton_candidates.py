"""Write bounded, read-only HGOL ownership diagnostics for a user-supplied file.

This headless tool does not import a scene or resolve ambiguous ownership. It
exports offsets, counts, digests and differing field paths, not native buffers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types


package = types.ModuleType('skeleton_inspection_cli')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from skeleton_inspection_cli.skeleton import scan_skeleton_candidates
from skeleton_inspection_cli.skeleton_diagnostics import skeleton_candidate_report


def _source_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Uncompressed native GHG file to inspect; never modified')
    parser.add_argument('--output', type=Path, required=True, help='New JSON report path; existing files are protected')
    parser.add_argument('--with-display', action='store_true',
                        help='Try the existing mesh/display decoders for structural compatibility checks')
    parser.add_argument('--expected-nodes', type=int,
                        help='Validate a joint count after identity selection; never select by count')
    parser.add_argument('--max-candidates', type=int, default=64, help='Candidate/name-table detail limit (1-256; selection still examines all)')
    parser.add_argument('--max-errors', type=int, default=64, help='Parse-error detail limit (1-256)')
    parser.add_argument('--max-relationships', type=int, default=128, help='Span-relationship detail limit (1-2048)')
    parser.add_argument('--max-differences', type=int, default=32, help='Differing field-path/display-index detail limit (1-128)')
    args = parser.parse_args(argv)
    if args.expected_nodes is not None and not 1 <= args.expected_nodes <= 255:
        parser.error('--expected-nodes must be from 1 to 255')
    try:
        if args.output.resolve() == args.source.resolve() or args.output.exists() or args.output.is_symlink():
            raise ValueError('Choose a new output file; the source, existing files and symlinks are protected')
        scan = scan_skeleton_candidates(args.source)
        display = None
        model = None
        display_check = dict(requested=args.with_display, status='not_requested')
        if args.with_display:
            from skeleton_inspection_cli.native_mesh import read_mesh
            from skeleton_inspection_cli.native_display import read_display
            try:
                model = read_mesh(args.source)
                if model['source_sha256'] != scan['source_sha256']:
                    raise ValueError('Source changed between skeleton and mesh reads')
                display = read_display(args.source, len(model['parts']))
                display_check.update(status='decoded', mesh_version=model['mesh_version'],
                                     mesh_parts=len(model['parts']), display_version=display['version'],
                                     display_specials=len(display['specials']),
                                     note='Existing display decoder output is structural compatibility evidence only.')
            except (OSError, ValueError, KeyError, TypeError) as error:
                model = None
                display_check.update(status='unavailable', detail=str(error)[:1024],
                                     detail_truncated=len(str(error)) > 1024,
                                     note='Selection diagnostics below use skeleton structure only; display compatibility was not checked.')
        report = skeleton_candidate_report(
            scan, display=display, mesh=model, expected_nodes=args.expected_nodes,
            max_candidates=args.max_candidates, max_errors=args.max_errors,
            max_relationships=args.max_relationships, max_differences=args.max_differences,
        )
        if _source_digest(args.source) != scan['source_sha256']:
            raise ValueError('Source changed during inspection; no report was written')
        report['source']['sha256_rechecked'] = True
        report['display_check'] = display_check
        rendered = json.dumps(report, indent=2, allow_nan=False) + '\n'
        with args.output.open('x', encoding='utf-8') as output:
            output.write(rendered)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Report written: {args.output}; skeleton selection: {report['selection']['outcome']}; "
          f"{report['scan']['parsed_candidates']} parsed candidates. Structural evidence is not a visual or in-game check.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
