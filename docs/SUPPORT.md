# Support and validation

The repository import is a reorganization of existing work, not a claim that
all formats or games are now supported.

- CU3: observed LMSH1/LB3 structures, matching source skeletons, packed curves,
  name rebuilding, hash/layout-locked GHG face target editing. DCSV is partial.
  Full scene assembly is still a private research pipeline. The V5 face helper
  requires actual companion meshes and verified material flags.
- LSW1 HGP: original PC character reader; ten headers in the prior local sample
  remain unsupported. Version 0.1.3 corrects palette color-space handling;
  color/material-role checks cover 1,827 records in 139 readable files.
- LIJ1 prototype: two original files verified, four DDS textures and 38 stored
  mip levels. Unsupported formats and layouts are refused.
- AN4: observed ANI-D six-channel layouts, constants and packed type-6/7 curves.
  The standalone skeleton reader expects the verified 63-joint HGOL v10 rig.
- 3DS BTGA: observed 56-byte texture header, PICA tiles, stored mips. The FUSE
  helper reads indexed payloads; it does not unpack encrypted ROMs.

Character projects, LOTDK mapping and Fortnite tools are intentionally excluded
from the public source. They remain in the private migrated archive.

Run portable checks manually with `python tools/check_repository.py`.
Blender-dependent and original-file tests are documented in each component.
There are no scheduled checks or CI workflows in this first version.
