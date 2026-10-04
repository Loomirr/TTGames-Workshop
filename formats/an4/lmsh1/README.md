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

BVH is an experimental transform preview. It does not preserve meshes, native
attachment events, visibility, gameplay notifies or all rig semantics. The
`sample_rotation.py` helper, used inside Blender, reconstructs quaternion
endpoints and shortest-hemisphere normalized interpolation to avoid Euler
snapping. BVH output alone does not apply that corrected interpolation.

## PAK helper

`unpack_pak.py` recognizes the observed `0x1234567a` wrapper. TT DFLT decoding
uses an external QuickBMS executable and Luigi Auriemma's ttgames.bms; neither
is bundled. Supply both explicitly:

```sh
python unpack_pak.py input.PAK output --quickbms path/to/quickbms.exe --bms path/to/ttgames.bms
```

The decoder is specific to observed versions. Verify output against the native
rig and retain original inputs. Do not apply this mapping to LOTDK raw Euler
channels; LOTDK retargeting requires its own rest-pose calibration.
