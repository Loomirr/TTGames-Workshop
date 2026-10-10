"""Read-only transfer planning for observed skeleton/AN4 layouts.

Produces mapping candidates, binding differences and explicit export blockers.
It does not modify native files, install a mod or certify cross-game binding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

try:
    from .rotation import validate_axis_bridge
except ImportError:
    from rotation import validate_axis_bridge

ROOT = Path(__file__).resolve().parents[2]
package = types.ModuleType("tt_transfer_readers")
package.__path__ = [str(ROOT / "formats/cu3/Addon/io_scene_lego_cu3")]
sys.modules[package.__name__] = package
from tt_transfer_readers.skeleton import read_skeleton, skeleton_identity
from tt_transfer_readers.an4 import AnimationFile

MAX_INPUT = 256 * 1024 * 1024


def snapshot(path):
    path = Path(path)
    if path.stat().st_size > MAX_INPUT:
        raise ValueError("Input exceeds the 256 MiB inspection limit: " + str(path))
    data = path.read_bytes()
    if len(data) > MAX_INPUT:
        raise ValueError("Input grew beyond the inspection limit")
    return dict(path=str(path.resolve()), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def unchanged(info):
    if snapshot(info["path"]) != info:
        raise ValueError("An input changed during transfer planning")


def load_rig(path):
    info = snapshot(path)
    if Path(path).suffix.casefold() not in (".ghg", ".json"):
        raise ValueError("Use an uncompressed GHG or a decoded skeleton JSON")
    rig = read_skeleton(path)
    unchanged(info)
    return rig, dict(**info, skeleton_identity=skeleton_identity(rig),
                     version=rig.get("version"), byte_order=rig.get("byte_order"),
                     joints=len(rig["joints"]),
                     selection=rig.get("selection"),
                     evidence="user-supplied decoded reference; native byte ownership not proven"
                     if Path(path).suffix.casefold() == ".json" else
                     "existing gated native decoder and ownership selection")


def bone_plan(donor, recipient, mapping=None):
    sources = {j["name"]: j for j in donor["joints"]}
    targets = {j["name"]: j for j in recipient["joints"]}
    explicit = mapping is not None
    if explicit:
        if not isinstance(mapping, dict) or set(mapping) != {"bones"} or not isinstance(mapping["bones"], list):
            raise ValueError("Mapping must contain only a bones list")
        rows = mapping["bones"]
        if len(rows) > 255:
            raise ValueError("Too many bone mappings")
    else:
        rows = [dict(source=name, target=name) for name in targets if name in sources]
    seen_source, seen_target, result = set(), set(), []
    target_by_source = {row.get("source"): row.get("target") for row in rows if isinstance(row, dict)}
    for row in rows:
        if (not isinstance(row, dict) or set(row) - {"source", "target", "axis_bridge_row_major"} or
                not isinstance(row.get("source"), str) or not isinstance(row.get("target"), str)):
            raise ValueError("Each mapping needs source/target names and an optional axis bridge")
        source, target = row["source"], row["target"]
        if source not in sources or target not in targets:
            raise ValueError("Unknown source/target bone in mapping")
        if source in seen_source or target in seen_target:
            raise ValueError("This planner requires a one-to-one mapping")
        seen_source.add(source)
        seen_target.add(target)
        sj, tj = sources[source], targets[target]
        sp = donor["joints"][sj["parent"]]["name"] if sj["parent"] is not None else None
        tp = recipient["joints"][tj["parent"]]["name"] if tj["parent"] is not None else None
        parent_matches = ((sp is None and tp is None) or
                          (sp is not None and sp in target_by_source and target_by_source[sp] == tp))
        bridge = row.get("axis_bridge_row_major")
        if bridge is not None:
            validate_axis_bridge(bridge)
        result.append(dict(source=source, source_index=sj["index"], target=target,
                           target_index=tj["index"], source_parent=sp, target_parent=tp,
                           mapped_parent_matches=parent_matches,
                           local_rest_identical=sj["local_bind_row_major"] == tj["local_bind_row_major"],
                           inverse_bind_identical=sj["inverse_world_bind_row_major"] == tj["inverse_world_bind_row_major"],
                           native_orientation_identical=sj.get("orient_row_major") == tj.get("orient_row_major"),
                           axis_bridge_row_major=bridge,
                           status="explicit mapping" if explicit else "name match proposed; unconfirmed"))
    return dict(mappings=result, explicit_mapping=explicit,
                unmapped_source=[n for n in sources if n not in seen_source],
                unmapped_target=[n for n in targets if n not in seen_target],
                policy="Unmapped targets retain their rest pose in a future preview; no ordinal/count-based remap")


def animation_plan(path, actor_name, rig):
    info = snapshot(path)
    cut = AnimationFile(path)
    unchanged(info)
    actors = [a for a in cut.actors if a["name"] == actor_name]
    if len(actors) != 1:
        raise ValueError("Animation requires one exact --actor name; available: " +
                         ", ".join(a["name"] for a in cut.actors))
    actor = actors[0]
    clips = []
    for rec in actor["records"]:
        anim = rec["animation"]
        status, issue = "sampleable", None
        try:
            anim.prepare(scene_channels=True)
            if anim.curves not in (6, 9) or getattr(anim, "discrete_scene_controls", False):
                raise ValueError("This is not a supported skeletal pose record")
        except ValueError as error:
            status, issue = "inspection only", str(error)
        clips.append(dict(name=rec["name"], nodes=anim.nodes, frames=anim.frames,
                          format=anim.header()["format"], curves=anim.curves,
                          node_count_matches=anim.nodes == len(rig["joints"]),
                          sampling=status, issue=issue))
    return dict(source=info, version=cut.version, actor=actor["name"],
                parent_actor=None if actor["parent"] is None else cut.actors[actor["parent"]]["name"],
                clips=clips, binding_status="explicit actor selection only; AN4 contains no bind table",
                required="Verify declared AS/CD resource, parent attachment and donor skeleton identity; name/count alone is insufficient")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--recipient", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, help="Explicit one-to-one bone mapping JSON")
    parser.add_argument("--animation", type=Path, action="append", default=[])
    parser.add_argument("--actor", default="", help="Exact AN4 actor, required with --animation")
    parser.add_argument("--output", type=Path, required=True, help="New report file; never overwritten")
    args = parser.parse_args(argv)
    try:
        if len(args.animation) > 128:
            raise ValueError("At most 128 animation sources per plan")
        inputs = [args.donor, args.recipient, *args.animation]
        if args.mapping:
            inputs.append(args.mapping)
        if args.output.exists() or args.output.is_symlink() or args.output.resolve() in {p.resolve() for p in inputs}:
            raise ValueError("Choose a new output path; sources and existing files are protected")
        if args.animation and not args.actor:
            raise ValueError("--actor is required with --animation")
        donor, donor_info = load_rig(args.donor)
        recipient, recipient_info = load_rig(args.recipient)
        mapping_info, mapping = None, None
        if args.mapping:
            mapping_info = snapshot(args.mapping)
            mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
            unchanged(mapping_info)
        mapping_plan = bone_plan(donor, recipient, mapping)
        animations = [animation_plan(p, args.actor, donor) for p in args.animation]
        blockers = ["Native cross-game GHG/AS/CPD/AN4 transplant export is not enabled by this planner",
                    "Mesh palettes, bind-space fitting, every LOD and draw ownership require validation",
                    "Grip/attachment locators and separate body/weapon/face action routing require validation",
                    "Root motion, scale animation, gameplay triggers and source shader compatibility need separate policies",
                    "Blender visual and actual target-game checks remain required"]
        if not mapping_plan["explicit_mapping"]:
            blockers.append("Proposed bone name matches have not been confirmed")
        if any(not r["mapped_parent_matches"] for r in mapping_plan["mappings"]):
            blockers.append("Mapped hierarchy differs; direct local rotation transfer is not sufficient")
        if any(r["axis_bridge_row_major"] is None for r in mapping_plan["mappings"]):
            blockers.append("Per-bone delta axis bridges have not been supplied")
        if mapping_plan["unmapped_target"]:
            blockers.append("Some target bones are unmapped; no animation is fabricated")
        for info in (donor_info, recipient_info):
            unchanged({k: info[k] for k in ("path", "bytes", "sha256")})
        for animation in animations:
            unchanged(animation["source"])
        if mapping_info:
            unchanged(mapping_info)
        report = dict(schema="tt.skeleton-transfer-plan.v1", stage="read-only planning",
                      donor=donor_info, recipient=recipient_info, mapping_source=mapping_info,
                      bone_plan=mapping_plan, animations=animations,
                      attachment_markers=dict(donor=[p["name"] for p in donor.get("points_of_interest", [])],
                                              recipient=[p["name"] for p in recipient.get("points_of_interest", [])]),
                      export_enabled=False, blockers=blockers,
                      source_files_modified=False, installed_game_modified=False)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Plan written: {args.output}; {len(mapping_plan['mappings'])} bone matches; native export remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
