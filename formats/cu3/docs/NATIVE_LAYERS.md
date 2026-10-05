# Native model layer selection

Character 0.4.3 / CU3 0.1.10 also select the nearest native accessory LOD
when a special has a verified distance-threshold/consecutive-clip table.
This is separate from HGOL layer alternatives: a named costume layer keeps
its authored selection. Stage pool interpretation is unchanged. See the
[minifigure patch notes](../../../docs/ISSUE_1_MINIFIGS.md).

A visible HGOL layer can contain several alternative display specials. Turning
on the layer does not mean drawing every special in it.

The observed LB3 `SUPER_MINIFIG` body has regular, robot and skeleton arms in
the same arm layer. The shared cape has both a bat cape and a regular cape in
its first layer. Importing all of these together caused overlapping geometry.

The importer now reads `Character Layer Special` records from the character
definition:

- A named selection chooses that exact display special in the layer.
- `All` retains every special in that layer, including intentional face/depth
  combinations and multipart breakup layers.
- A layer without an override uses its first special. This is the observed
  default for the ordinary minifigure and bat-cape definitions.
- A model inspected without a character definition keeps all alternatives;
  the importer cannot infer which costume configuration the user wants.

The layer mask still decides which layers are enabled. Selection happens
inside those layers. Layer indices come from the native table, including
indices above 31, rather than being guessed from mesh names. NXG definitions
name the selector field `Layer Id`; the observed DX11 definitions use `Layer`.
Named selections that do not identify one special, conflicting overrides and
inconsistent metadata are rejected.

An offline audit resolved 52 available LB3/LMSH1 character definitions without
a selection mismatch. In the Flash body this reduces 23 mesh-part draws to
13 while preserving the explicit head/depth pair. The regular-cape definitions
select `ComplexCape_Mesh`, and the black bat-cape definition defaults to
`ComplexBatCape_Mesh`. These are source-data and structural checks, not a new
frame-for-frame in-game validation. Runtime changes to layer-special selection
inside animation/control tracks remain separate research.

Run the asset-free selection checks with:

```sh
python formats/cu3/scripts/test_native_layers.py
```
