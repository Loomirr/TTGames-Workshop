# LEGO Indiana Jones 1 — Xbox 360 prototype

Use the [NU20 DDS extractor](../../formats/nu20/lij1-xbox360/README.md).
Version 0.1.2 handles observed GHG/GSC, standalone TEX, Xbox 360 font textures
and existing PC DDS files. It exports BC1/2/3/5, float textures and six-face
cubemaps. All 757 supplied GHG/GSC files process; nine undersized allocations
remain explicitly raw, and objects without mip metadata export base images
with warnings. See the component README and FORMAT.md for validation and limits.
