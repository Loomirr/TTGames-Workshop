"""Inspect, sample or transform one existing LSW1 PC animation channel."""
import argparse
import json
from pathlib import Path
from animation_records import AnimationRecords, AnimationError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'sample', 'sample-layers', 'transform'))
    parser.add_argument('input', type=Path)
    parser.add_argument('--family', required=True, choices=('ANI', 'BSA'))
    parser.add_argument('--details', action='store_true', help='Include stored keys and lookup frames')
    parser.add_argument('--track', type=int)
    parser.add_argument('--component', type=int)
    parser.add_argument('--layers', type=int, nargs='+', help='Explicit native HGP layer indices for BSA sample-layers')
    parser.add_argument('--time', type=float, help='One-based native frame time for sample; not seconds')
    parser.add_argument('--scale', type=float, default=1.0)
    parser.add_argument('--offset', type=float, default=0.0)
    parser.add_argument('--source-sha256', help='Hash from inspect, required for edits')
    parser.add_argument('--output', type=Path, help='New separate output file; never overwritten')
    args = parser.parse_args(argv)
    try:
        # Bound the read itself, including files growing between stat and read.
        with args.input.open('rb') as stream:
            data = stream.read(AnimationRecords.MAX_BYTES + 1)
        clip = AnimationRecords(data, args.family)
        report = clip.summary()
        if args.layers is not None and args.operation != 'sample-layers':
            parser.error('--layers belongs to sample-layers')
        if args.operation == 'inspect':
            if args.output is not None or args.track is not None or args.component is not None or args.time is not None:
                parser.error('inspect writes JSON to standard output; edit options require transform')
            if args.details:
                report['channels'] = clip.records
                report['track_flags'] = list(clip.flags)
        elif args.operation == 'sample':
            if args.track is None or args.component is None or args.time is None:
                parser.error('sample requires --track, --component and --time')
            if args.output is not None:
                parser.error('sample writes JSON to standard output')
            report['sample'] = dict(track=args.track, component=args.component, time=args.time,
                                    value=clip.evaluate_channel(args.track, args.component, args.time))
        elif args.operation == 'sample-layers':
            from face_channels import sample_layers
            if args.layers is None or args.time is None or args.family != 'BSA':
                parser.error('sample-layers requires --family BSA, --layers and --time')
            if args.output is not None or args.track is not None or args.component is not None:
                parser.error('sample-layers uses layer indices and writes decoded JSON to standard output')
            report['layer_sample'] = dict(time=args.time, layers=args.layers,
                values=sample_layers(clip, args.time, args.layers),
                scope='Decoded BSA layer channels; no automatic morph-target binding')
        else:
            if args.time is not None:
                parser.error('--time belongs to sample; transform edits the whole stored channel')
            if args.output is None or args.track is None or args.component is None or not args.source_sha256:
                parser.error('transform requires --output, --track, --component and --source-sha256')
            if args.output.resolve() == args.input.resolve():
                parser.error('Choose a separate output file')
            result = clip.transform_channel(args.track, args.component, scale=args.scale,
                                            offset=args.offset, expected_sha256=args.source_sha256)
            # Exclusive creation also protects aliases, symlinks and racing writers.
            with args.output.open('xb') as stream:
                stream.write(result)
            report['output'] = str(args.output)
            report['edited'] = AnimationRecords(result, args.family).summary()
        print(json.dumps(report, indent=2))
    except (OSError, AnimationError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
