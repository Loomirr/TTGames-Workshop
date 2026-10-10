"""Export decoded channels as experimental BVH files for a visual rig check.

Animation scalar sampling is verified separately. This exporter assumes
absolute local transforms and XYZ engine Euler angles, reflecting Z into a
right-handed Y-up frame. Full Marvel hierarchy evaluation is not yet verified.
FPS is an explicit user-selectable assumption, not read from AN4.
"""
import argparse
import json
import math
from pathlib import Path


def export(clip, rig, fps):
    joints = rig['joints']
    if clip['node_count'] != len(joints):
        raise ValueError('Joint count mismatch')
    children = {i: [] for i in range(len(joints))}
    roots = []
    for i, joint in enumerate(joints):
        if joint['parent'] is None:
            roots.append(i)
        else:
            children[joint['parent']].append(i)
    if len(roots) != 1:
        raise ValueError('BVH requires one root')
    lines, order, offsets = ['HIERARCHY'], [], {}
    def visit(index, level):
        joint = joints[index]
        indent = '  ' * level
        lines.extend([f"{indent}{'ROOT' if level == 0 else 'JOINT'} {joint['name']}", indent + '{'])
        offset = joint['local_bind_row_major'][12:15]
        offsets[index] = offset
        lines.append(indent + '  OFFSET ' + ' '.join(f'{x:.9g}' for x in offset))
        # BVH's intrinsic ZYX order matches Rz * Ry * Rx from the engine helper.
        lines.append(indent + '  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation')
        order.append(index)
        for child in children[index]:
            visit(child, level + 1)
        if not children[index]:
            lines.extend([indent + '  End Site', indent + '  {', indent + '    OFFSET 0 0.005 0', indent + '  }'])
        lines.append(indent + '}')
    visit(roots[0], 0)
    lines.extend(['MOTION', f"Frames: {clip['frame_count']}", f'Frame Time: {1/fps:.12g}'])
    for frame in clip['samples']:
        values = []
        for index in order:
            tx, ty, tz, rx, ry, rz = frame[index]
            # Blender's BVH armature importer subtracts OFFSET itself for all
            # joints with position channels. Supply absolute local positions.
            values.extend([tx, ty, -tz, math.degrees(rz), -math.degrees(ry), -math.degrees(rx)])
        lines.append(' '.join(f'{x:.9g}' for x in values))
    # Check the actual serialized motion rows against declared channel count.
    start = lines.index('MOTION') + 3
    assert len(lines[start:]) == clip['frame_count']
    assert all(len(row.split()) == len(joints)*6 for row in lines[start:])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decoded', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--fps', type=float, default=30)
    args = parser.parse_args(argv)
    if not 0 < args.fps < 1000:
        parser.error('FPS must be positive and below 1000')
    try:
        rig = json.loads((args.decoded / 'skeleton.json').read_text())
        manifest = json.loads((args.decoded / 'decode-manifest.json').read_text())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.destination.exists():
        parser.error('Choose a new BVH output folder')
    args.destination.mkdir(parents=True)
    records = []
    for item in manifest:
        if item['status'] != 'decoded_scalars':
            continue
        source = Path(item['output'])
        clip = json.loads(source.read_text())
        # Flat names stay below Windows legacy path limits used by some importers.
        target = args.destination / (clip['sha256'][:8] + '__' + source.with_suffix('.bvh').name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(export(clip, rig, args.fps))
        records.append(dict(source=str(source), output=str(target.resolve()), frames=clip['frame_count']))
    (args.destination / 'export-manifest.json').write_text(json.dumps(dict(
        status='experimental_transform_mapping_not_visually_verified' if records else 'no_decoded_clips',
        fps_assumption=args.fps, units='original game units', clips=records), indent=2))
    print(f'Exported {len(records)} experimental BVH files at assumed {args.fps:g} FPS')


if __name__ == '__main__':
    main()
