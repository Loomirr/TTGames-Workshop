# LMSH1 AN4 research tools

These are the portable decoder pieces from our original Marvel animation work.
They are not a universal animation importer. Character-specific extraction,
source scene, audio and retargeting experiments remain in the local archive.

## Decode observed source clips

With Python 3 and extracted, uncompressed files:

```sh
python decode_an4.py path/to/clips path/to/SUPER_MINIFIG_NXG.ghg path/to/decoded --actor ExactActorName
python export_bvh.py path/to/decoded path/to/bvh --fps 30
```

The skeleton reader expects the verified HGOL v10 63-joint Marvel rig. The CLI
requires an explicit `--actor` and accepts `--clip-index`; the Python `animation`
function accepts `actor_name` and `clip_index`. Source scalar JSON preserves original channels.
Unsupported layouts are recorded in the decode manifest.
Choose new decode and BVH output folders. A decode set with no supported clips
produces an empty BVH export manifest (`no_decoded_clips`); it is not a successful
animation conversion. Unverified skeleton layouts are refused before output is created.

BVH is an experimental transform preview. It does not preserve meshes, native
attachment events, visibility, gameplay notifies or all rig semantics. The
`sample_rotation.py` helper, used inside Blender, reconstructs quaternion
endpoints and shortest-hemisphere normalized interpolation to avoid Euler
snapping. BVH output alone does not apply that corrected interpolation.

## PAK helper

`unpack_pak.py` recognizes the observed `0x1234567a` wrapper and now uses the
Workshop's existing Python `Deflate_v1.0` decoder. Run it from a complete
Workshop source tree; its shared readers live in the CU3 addon directory but
do not import Blender. QuickBMS and a BMS script are no longer required or
invoked. The old `--quickbms` and `--bms` options remain accepted, with no effect,
for existing commands:

```sh
python unpack_pak.py input.PAK new-output
```

Choose a new output parent folder. A single PAK produces
`new-output/input/`, containing its members and `pak-manifest.json`. The
manifest records the source and extracted hashes, stored/decoded lengths and
the actual publication method. Existing output folders are preserved.

The complete member list is checked before any decoding or output: path
traversal, Windows reserved names, case aliases, duplicate files, file/directory
collisions, invalid metadata/payload extents and declared size limits are
rejected. The bank and each member are limited to 256 MiB; cumulative packed
and decoded output is limited to 1 GiB. The Python API accepts lower limits.
Decoded sizes must match, whole bytes after the final TT compression block
are rejected, and recursively wrapped TT members remain unsupported.

Each PAK is streamed into an owned sibling staging directory, verified, then
published with a non-replacing rename. A late decoder or write failure leaves
no completed folder for that PAK. Directory input is preflighted as a batch,
but publication is per PAK: an error in a later PAK may leave earlier, fully
verified PAK folders. A batch is not an all-or-nothing transaction. No
cross-filesystem atomicity or power-loss durability is claimed.

These checks do not establish LOTR DAT mode-3 DFLT framing or its codec; that
mode is still rejected. No original game specimens were available for this
safety update. The new tests verify synthetic bounds/refusals and the existing
TT wrapper algorithm, not new game/platform compatibility.

```sh
python ../../cu3/scripts/test_pak_preflight.py
```

The decoder is specific to observed versions. Verify output against the native
rig and retain original inputs. Do not apply this mapping to LOTDK raw Euler
channels; LOTDK retargeting requires its own rest-pose calibration.
