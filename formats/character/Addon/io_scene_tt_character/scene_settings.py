"""Idempotent registration of character import and viewing-copy settings.

An enabled addon can outlive one or more Scene properties during an in-session
update. Restore missing definitions at an operator boundary, without replacing
registered properties or changing their values. A property whose value Blender
has already discarded returns to its documented default.
"""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty


PREVIEW_FIELDS = (
    'tt_face_detail', 'tt_preview_normals', 'tt_preview_normal_strength',
    'tt_preview_shading', 'tt_preview_display', 'tt_preview_exposure',
    'tt_preview_samples',
)

_DEFINITIONS = (
    ('tt_mesh_detail', EnumProperty, dict(name='Mesh detail', items=[
        ('HIGHEST', 'Highest detail', 'Use the nearest verified native LOD for all imported character parts'),
        ('AUTHORED', 'Authored binding', 'Inspect the original display binding')], default='HIGHEST')),
    ('tt_costume_layers', EnumProperty, dict(name='Costume', items=[
        ('default', 'Gameplay', 'Native default character layers'),
        ('cutscene', 'Cutscene', 'Native cutscene layers'),
        ('authored', 'Authored flags', 'Original definition selection flags')], default='default')),
    ('tt_import_attachments', BoolProperty, dict(name='Import attachments', default=True)),
    ('tt_face_detail', IntProperty, dict(name='Face clipping quality', default=4, min=0, max=4,
        description='Higher values reduce clipping steps but cost more during playback; affects viewing copy only')),
    ('tt_preview_normals', BoolProperty, dict(name='Use normal maps', default=True)),
    ('tt_preview_normal_strength', FloatProperty, dict(name='Normal strength', default=1.0, min=0, max=2,
        description='Viewing-copy multiplier for normal maps; 1 preserves imported strength. This is not a verified game shader value')),
    ('tt_preview_shading', EnumProperty, dict(name='Shading', items=[
        ('LIT', 'Lit materials', 'Source material reconstruction under scene lighting'),
        ('ALBEDO', 'Base color', 'Unlit base color and alpha for checking texture/color reconstruction')], default='LIT')),
    ('tt_preview_display', EnumProperty, dict(name='Color display', items=[
        ('Standard', 'Standard', 'sRGB display without filmic tone mapping'),
        ('AgX', 'AgX', 'Filmic tone mapping for strong lighting')], default='Standard')),
    ('tt_preview_exposure', FloatProperty, dict(name='Exposure', default=0, min=-5, max=5)),
    ('tt_preview_samples', IntProperty, dict(name='Render samples', default=64, min=1, max=1024)),
)


def missing_scene_settings():
    return tuple(name for name, _, _ in _DEFINITIONS if not hasattr(bpy.types.Scene, name))


def ensure_scene_settings():
    """Restore only missing RNA definitions; keep existing settings intact."""
    restored = []
    for name, factory, options in _DEFINITIONS:
        if not hasattr(bpy.types.Scene, name):
            setattr(bpy.types.Scene, name, factory(**options))
            restored.append(name)
    return tuple(restored)


def unregister_scene_settings():
    for name, _, _ in reversed(_DEFINITIONS):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
