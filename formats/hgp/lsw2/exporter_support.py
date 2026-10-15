"""Helpers shared by the importer and the exporter."""


def pixel_hash(img):
    """Fingerprint of an image's pixels: the exporter re-encodes a texture only if it changed."""
    import hashlib
    import numpy as np
    px = np.empty(img.size[0] * img.size[1] * img.channels, dtype=np.float32)
    img.pixels.foreach_get(px)
    return hashlib.sha1(px.tobytes()).hexdigest()
