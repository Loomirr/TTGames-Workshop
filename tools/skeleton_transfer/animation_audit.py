"""Read-only native AN4 comparison; decoded agreement is not runtime approval."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
package = types.ModuleType("tt_transfer_audit_readers")
package.__path__ = [str(ROOT / "formats/cu3/Addon/io_scene_lego_cu3")]
sys.modules[package.__name__] = package
from tt_transfer_audit_readers.an4 import AnimationFile

MAX_INPUT = 256 * 1024 * 1024
MAX_SAMPLE_VALUES = 2_000_000


def metadata(animation):
    return dict(byte_order=animation.endian, magic=animation.magic.decode("ascii"),
                nodes=animation.nodes, curves=animation.curves, keys=animation.keys,
                stride=animation.stride, frames=animation.frames,
                old_frames=animation.old_frames, old_first=animation.old_first,
                first=animation.first, ratio=animation.ratio, flags=animation.flags,
                integer_constant_count=animation.integer_constant_count,
                minimum=animation.minimum, scale=animation.scale,
                auxiliary_offsets=list(animation.offsets[5:]))


def compare_record(original, candidate, changed_bones=(), sample_step=0.25):
    """Compare scalar poses and declarations without guessing game semantics.

    A declared changed bone excludes its numeric channels from the unchanged
    maximum, but does not excuse byte-order, timeline or flag changes. Scale
    channels disabled by native node flags use unit scale for comparison.
    """
    if not math.isfinite(sample_step) or not 0.01 <= sample_step <= 1:
        raise ValueError("Sample step must be finite and between 0.01 and 1 frame")
    changed_bones = set(changed_bones)
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < original.nodes
           for i in changed_bones):
        raise ValueError("Changed bone indices must belong to the original clip")
    before, after = metadata(original), metadata(candidate)
    differences = {key: dict(original=value, candidate=after[key])
                   for key, value in before.items() if value != after[key]}
    notices = []
    for key in ("byte_order", "magic", "nodes", "curves", "frames", "first",
                "old_first", "old_frames", "flags", "ratio", "keys",
                "integer_constant_count", "auxiliary_offsets"):
        if key in differences:
            notices.append("Native declaration changed: " + key)
    flags = [dict(bone=i, original=a, candidate=b, declared_changed=i in changed_bones)
             for i, (a, b) in enumerate(zip(original.node_flags, candidate.node_flags)) if a != b]
    if flags:
        notices.append("Bone channel/bind/scale flags changed; scalar equality alone does not validate these")
    report = dict(original=before, candidate=after, metadata_changes=differences,
                  node_flag_changes=flags, declared_changed_bones=sorted(changed_bones),
                  notices=notices, sampling="not performed")
    if original.nodes != candidate.nodes or original.curves != candidate.curves:
        return report
    # Bound work before preparing or sampling a potentially large user file.
    end = max(original.frames, candidate.frames) - 1
    intervals = math.ceil(max(0, end) / sample_step)
    count = intervals + 1
    if count * original.nodes * original.curves * 2 > MAX_SAMPLE_VALUES:
        raise ValueError("Comparison exceeds the bounded scalar sampling budget; use a larger step")
    original.prepare(scene_channels=True)
    candidate.prepare(scene_channels=True)
    maximum = [0.0] * original.nodes
    worst = None
    for index in range(count):
        frame = min(end, index * sample_step)
        a, b = original.sample(frame), candidate.sample(frame)
        for node in range(original.nodes):
            for channel in range(original.curves):
                av, bv = a[node][channel], b[node][channel]
                if original.curves == 9 and channel >= 6:
                    if not original.node_flags[node] & 8:
                        av = 1.0
                    if not candidate.node_flags[node] & 8:
                        bv = 1.0
                error = abs(av - bv)
                if not math.isfinite(error):
                    raise ValueError("Non-finite decoded comparison")
                maximum[node] = max(maximum[node], error)
                if node not in changed_bones and (worst is None or error > worst["error"]):
                    worst = dict(frame=frame, bone=node, channel=channel,
                                 original=av, candidate=bv, error=error)
    report.update(sampling="decoded scalar comparison; rotations are raw angular channels, not a pose-distance metric",
                  sample_step=sample_step, sampled_times=count,
                  maximum_channel_error_by_bone=maximum,
                  maximum_undeclared_channel_error=max((v for i, v in enumerate(maximum)
                                                       if i not in changed_bones), default=0.0),
                  worst_undeclared_sample=worst)
    return report


def _records(file, actor_name):
    found = {}
    for actor in file.actors:
        if actor_name and actor["name"] != actor_name:
            continue
        if actor["name"] in found:
            raise ValueError("Ambiguous repeated actor name; ownership requires separate resolution")
        records = {}
        for record in actor["records"]:
            if record["name"] in records:
                raise ValueError("Ambiguous repeated clip name; record ownership requires separate resolution")
            records[record["name"]] = record
        parent = actor["parent"]
        found[actor["name"]] = dict(parent=file.actors[parent]["name"] if parent is not None else None,
                                    records=records)
    if not found:
        raise ValueError("No exact requested actor in AN4")
    return found


def compare_files(original, candidate, actor_name="", changed_bones=(), sample_step=0.25):
    if not math.isfinite(sample_step) or not 0.01 <= sample_step <= 1:
        raise ValueError("Sample step must be finite and between 0.01 and 1 frame")
    if changed_bones and not actor_name:
        raise ValueError("Specify an exact actor when declaring changed bones")
    a, b = _records(original, actor_name), _records(candidate, actor_name)
    if a.keys() != b.keys():
        raise ValueError("Actor ownership changed between files")
    rows, sampled_values = [], 0
    for name, actor in a.items():
        other = b[name]
        if actor["parent"] != other["parent"] or actor["records"].keys() != other["records"].keys():
            raise ValueError("Actor parent or clip identities changed")
        for label, record in actor["records"].items():
            new = other["records"][label]
            old_anim, new_anim = record["animation"], new["animation"]
            if old_anim.nodes == new_anim.nodes and old_anim.curves == new_anim.curves:
                samples = math.ceil((max(old_anim.frames, new_anim.frames) - 1) / sample_step) + 1
                sampled_values += samples * old_anim.nodes * old_anim.curves * 2
                if sampled_values > MAX_SAMPLE_VALUES:
                    raise ValueError("Whole-file comparison exceeds the bounded scalar sampling budget; choose an actor or larger step")
            row = compare_record(record["animation"], new["animation"], changed_bones, sample_step)
            row.update(actor=name, clip=label, parent=actor["parent"],
                       placement_matrix_unchanged=record["matrix"] == new["matrix"])
            rows.append(row)
    return dict(schema="tt.animation-transfer-audit.v1", native_export_certified=False,
                validation="Gated decoder and scalar comparison only; no target-game execution",
                source_version=original.version, candidate_version=candidate.version,
                version_unchanged=original.version == candidate.version, records=rows)


def _snapshot(path):
    path = Path(path)
    if path.stat().st_size > MAX_INPUT:
        raise ValueError("AN4 exceeds the 256 MiB inspection limit")
    with path.open("rb") as stream:
        data = stream.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("AN4 grew beyond the inspection limit")
    return data, dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--actor", default="")
    parser.add_argument("--changed-bone", type=int, action="append", default=[])
    parser.add_argument("--sample-step", type=float, default=0.25)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists() or out.resolve() in (Path(args.source).resolve(), Path(args.candidate).resolve()):
        parser.error("Choose a fresh report path outside the inputs")
    try:
        raw, source = _snapshot(args.source)
        edited, candidate = _snapshot(args.candidate)
        report = compare_files(AnimationFile(args.source, data=raw),
                               AnimationFile(args.candidate, data=edited), args.actor,
                               args.changed_bone, args.sample_step)
        if _snapshot(args.source)[1] != source or _snapshot(args.candidate)[1] != candidate:
            raise ValueError("An input changed during the audit")
        report.update(source=source, candidate=candidate)
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("Animation audit written; target-game validation remains separate")


if __name__ == "__main__":
    main()
