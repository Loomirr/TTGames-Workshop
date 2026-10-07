"""Viewing-copy controls; never rewrite imported/source material graphs."""
import json
import bpy
from .scene_settings import PREVIEW_FIELDS, ensure_scene_settings

FIELDS = PREVIEW_FIELDS


def copy_settings(source, destination):
    ensure_scene_settings()
    for field in FIELDS:
        setattr(destination, field, getattr(source, field))


def isolate_materials(scene):
    copies = {}
    for obj in scene.objects:
        if obj.type != 'MESH':continue
        for slot in obj.material_slots:
            material = slot.material
            if material and material not in copies:
                copy = material.copy(); copy.name = material.name + ' / Preview'
                copy['tt_preview_material'] = True
                copies[material] = copy
            if material:slot.material = copies[material]


def material_view(material, *, normals=True, normal_strength=1.0, albedo=False):
    if not material.get('tt_preview_material') or not material.node_tree:return
    tree = material.node_tree; nodes, links = tree.nodes, tree.links
    p = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if not p or not output:return  # Depth-only holdouts retain their shader.
    for node in nodes:
        if node.type == 'NORMAL_MAP':
            strength = node.inputs['Strength']
            if strength.is_linked:continue  # Keep authored procedural strength.
            if 'tt_preview_base_strength' not in node:
                node['tt_preview_base_strength'] = strength.default_value
            strength.default_value = node['tt_preview_base_strength'] * normal_strength
    normal = p.inputs['Normal']
    if 'tt_preview_normal_link' not in material:
        saved = [normal.links[0].from_node.name, normal.links[0].from_socket.name] if normal.is_linked else []
        material['tt_preview_normal_link'] = json.dumps(saved)
    saved = json.loads(material['tt_preview_normal_link'])
    for link in list(normal.links):links.remove(link)
    if normals and saved:links.new(nodes[saved[0]].outputs[saved[1]], normal)
    surface = output.inputs['Surface']
    if 'tt_preview_surface_link' not in material:
        saved_surface = [surface.links[0].from_node.name, surface.links[0].from_socket.name] if surface.is_linked else []
        material['tt_preview_surface_link'] = json.dumps(saved_surface)
    if albedo:
        emission = nodes.get('TT preview albedo') or nodes.new('ShaderNodeEmission')
        emission.name = 'TT preview albedo'; emission.inputs['Strength'].default_value = 1
        base = p.inputs['Base Color']
        if base.is_linked:links.new(base.links[0].from_socket, emission.inputs['Color'])
        else:emission.inputs['Color'].default_value = base.default_value
        transparent = nodes.get('TT preview transparent') or nodes.new('ShaderNodeBsdfTransparent')
        transparent.name = 'TT preview transparent'
        mix = nodes.get('TT preview alpha') or nodes.new('ShaderNodeMixShader'); mix.name = 'TT preview alpha'
        alpha = p.inputs['Alpha']
        if alpha.is_linked:links.new(alpha.links[0].from_socket, mix.inputs[0])
        else:mix.inputs[0].default_value = alpha.default_value
        links.new(transparent.outputs[0], mix.inputs[1]); links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], surface)
    else:
        saved_surface = json.loads(material['tt_preview_surface_link'])
        for link in list(surface.links):links.remove(link)
        if saved_surface:links.new(nodes[saved_surface[0]].outputs[saved_surface[1]], surface)


def apply_settings(context, scene):
    if not scene.get('tt_character_preview'):
        raise ValueError('Create a character preview scene first')
    ensure_scene_settings()
    materials = {m for o in scene.objects if o.type == 'MESH' for m in o.data.materials if m}
    for material in materials:
        material_view(material, normals=scene.tt_preview_normals,
                      normal_strength=scene.tt_preview_normal_strength,
                      albedo=scene.tt_preview_shading == 'ALBEDO')
    for obj in scene.objects:
        modifier = obj.modifiers.get('TT live facial clipping')
        if modifier and modifier.node_group:
            for node in modifier.node_group.nodes:
                if node.bl_idname == 'GeometryNodeSubdivideMesh':node.inputs['Level'].default_value = scene.tt_face_detail
    scene.view_settings.view_transform = scene.tt_preview_display
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = scene.tt_preview_exposure
    scene.view_settings.gamma = 1
    scene.cycles.samples = scene.tt_preview_samples
    if hasattr(scene, 'eevee') and hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = scene.tt_preview_samples
    if context.screen:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                shading = area.spaces.active.shading
                shading.type = 'MATERIAL'
                shading.use_scene_lights = True; shading.use_scene_world = True
