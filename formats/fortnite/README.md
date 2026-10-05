# LEGO Fortnite models and textures

Character addon **0.5.2** includes a separate **LEGO Fortnite** profile with a
searchable static model browser. It accepts exported CUE4Parse JSON metadata,
PNG textures and GLB meshes, preserving the meshes' UVs, skin and native rig.
It does not use the TT GHG/GSC/AN4 readers. Animations and Unreal asset writing
are unavailable for this profile.

## Use in Blender

1. Install the latest [character addon](../character/README.md).
2. Select **LEGO Fortnite** in **N sidebar > TT Character**.
3. Set **Game folder** to Fortnite's installation or its
   `FortniteGame/Content/Paks` folder. Configure the optional extractor and
   private settings below first. Existing libraries containing `Exports/` and
   `Models/` still work without an extractor.
4. Press **Browse game characters**, search a name or source codename and
   select it. Use Material Preview and NumPad `.` to inspect the selected parts.
   **Create static character preview scene** creates a separate viewing copy
   with a camera and lights, preserving the source scene and selected game.

The browser discovers dataless `COI_Figure_*_Dataless` recipes and assembled
`FigureBake_*` skeletal exports. A discovered entry can still be unsupported
or missing companions. Recipe imports require the shared preview body,
declared head/accessory models, native color LUT, material JSON and textures.
Duplicate basenames and unknown replacement roles are rejected.

An optional `character-names.json` in the export library maps source codenames
to display names. Without aliases, search uses source codenames. No character
names, asset manifests or game data are shipped with the addon.

## Optional installed-game extraction bridge

`Extractor/` contains our small .NET CLI bridge. It uses a separately supplied
CUE4Parse reader; external tools, archive keys, mappings and Oodle are not in
the addon or repository. This is an experimental source tool, not a bundled
ready-to-use Unreal extraction executable.

Build with .NET 10 and a reviewed CUE4Parse checkout:

```powershell
dotnet build formats/fortnite/Extractor/Workshop.Fortnite.Extractor.csproj -c Release -p:CUE4ParseRoot=D:/Dependencies/CUE4Parse
```

The checked reader is the `mutable` fork at
[`Bmarquez1997/CUE4Parse`](https://github.com/Bmarquez1997/CUE4Parse), commit
`d3148ad97362a73c046a6f17a317d973255bb073`, using `GAME_UE6_0`.
Its own build/native dependency instructions apply. A separately compiled,
reviewed dependency folder can instead be supplied as `CUE4ParseBinRoot`.
This binary-reference option does not make those dependencies ours or grant
permission to redistribute proprietary runtimes. The conversion reader is
Apache-2.0; no FortnitePorting or Unreal engine source is copied here.

Keep a settings JSON outside the public checkout:

```json
{
  "paks": "D:/Games/Fortnite/FortniteGame/Content/Paks",
  "output": "D:/Exports/LEGO-Fortnite",
  "engineVersion": "GAME_UE6_0",
  "mappings": "D:/Private/current-build.usmap",
  "keyFile": "D:/Private/current-build-keys.json",
  "oodle": "D:/Dependencies/oo2core_9_win64.dll"
}
```

The private key file follows the reviewed reader's existing JSON convention:
an outer `keys` object with `mainKey.key` and an `extraKeys` array of `guid`/`key`
objects. Supply data matching your installed build; the bridge does not fetch
keys, mappings, account credentials or binaries. Relative settings paths are
resolved against the settings file. Outputs must be outside the archive folder.

If your installation uses streamed assets, explicitly add an HTTPS `chunkHost`
setting for the appropriate asset CDN. This enables network chunk reads into
`StreamCache/`; leaving it out keeps extraction local.

Run `Workshop.Fortnite.Extractor index settings.json` to create
`lego-fortnite-index.json`. Or set **Optional LEGO Fortnite extractor** and
**Private Fortnite extractor settings** in the addon preferences. With an
installation/Paks source, the addon supplies `paks` and `output` automatically;
the template's values for those two fields are ignored. Mappings, key-file and
Oodle paths are resolved relative to the original template. The template and
game files are not changed; archive keys are not copied into generated settings.

Exports go into `fortnite/<build-id>/` under **Optional asset cache**, or the
platform's user cache (`TTGamesWorkshop/Cache`) when that preference is blank.
The cache must be separate from the game installation. Its build ID includes
archive paths, sizes and modification times, extractor options and dependency
file metadata. Updated archives or mappings select a new cache rather than
silently reusing old exports. Older cache folders remain available for manual
cleanup; this is a metadata fingerprint, not a hash of every archive payload.

Browsing builds an index when absent; selecting an unexported entry runs the
bridge before importing it. Existing exported-library mode keeps the previous
offline browsing: it does not start indexing just because an extractor is
configured. If explicitly using the bridge, its settings `output` must match
that library.
The extraction process runs in the background without a console window;
Blender remains responsive. **Refresh installed LEGO outfit index** rebuilds
discovery after a game update. `workshop-extractor.log` and `last-export.json`
record failures privately. A partial export is not proof of complete materials.
Missing required model/texture companions now trigger extraction again in
installed mode, including when a previous attempt wrote only partial output.
Unsupported selectors and layouts remain explicit errors rather than retries.

## Coverage and accuracy

- Checked offline assembly: Wolverine, Wolverine Zero, Weapon X and Pen & Ink
  Wolverine, from Fortnite **42.30**. Installed-game extraction and Blender
  assembly also cover Wolverine and Peely. Version 0.5.2 uses declared head
  material references rather than inferred filenames, supports the verified
  standard-head color selector when the material omits its color scalar, and
  deduplicates mounted sources. See [the broader import audit](../../docs/FORTNITE_IMPORT_AUDIT.md).
  The bridge's inventory finds other sources;
  they have not all been imported or visually verified.
- Default dataless body recipes currently accept native head and head-accessory
  roles. Replacement hands/legs, capes, other attachment roles, non-default body
  selectors and split upper/lower arm colors are rejected pending validation.
- Baked skeletal meshes use their own material slot references and source maps.
  Unrecognized shader parameters or multi-mesh assemblies are rejected.
- Reconstructed channels: plastic LUT colors, body and head alpha printing,
  accessory printing and DirectX normal maps. Source shader maps are retained
  for inspection. Native geometry, split vertices and UV channels remain intact,
  except removal of the shared body's placeholder head in favor of its declared
  head mesh. No rest-bone edits or animation retargeting are performed.
- Runtime eye/brow/mouth expression atlases and metallic, glitter, emissive,
  translucency and shader-mask effects remain incomplete. This is not full
  Unreal shader parity; a successful static import is not a fidelity certificate.
- Fortnite updates can change packages, mappings and Mutable layouts. Unknown
  layouts are rejected instead of inventing missing geometry or colors.
- The bridge decodes the highest serialized mip. Blender compares PNG sizes
  with native texture metadata and rejects reduced resident copies. Missing
  streamed payloads must be resolved before a textured import can finish.

The existing Wolverine-specific conversions and LOTDK mapper remain private.
This component contains reusable tool code only. See [licensing](../../docs/LICENSING.md).
