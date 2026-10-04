"""Display-referred LSW1 palette RGB to Blender's default scene-linear RGB."""
import math


def srgb_channel_to_linear(value):
    value=float(value)
    if not math.isfinite(value) or not 0.0<=value<=1.0:
        raise ValueError('Invalid original LSW1 diffuse color channel')
    return value/12.92 if value<=0.04045 else ((value+0.055)/1.055)**2.4


def diffuse_to_linear(rgb):
    if len(rgb)!=3:
        raise ValueError('Expected three original LSW1 diffuse color channels')
    return tuple(srgb_channel_to_linear(value) for value in rgb)
