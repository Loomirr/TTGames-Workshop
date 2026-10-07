"""Character-definition costume slots, using the user's native TEX files."""
import tempfile
import uuid
import math
from pathlib import Path
import bpy
from .cu3 import FormatError
from .material_preview import attach_vertex_albedo, attach_vertex_opacity, attach_normal_map
from .texture_store import read_texture_store
from .dds import read_embedded_dds
from .native_materials import costume_slot, costume_uv_index, surface_normal_binding
from .profiles import active_renderer_reference
from .material_capabilities import material_capability_report
from .dependencies import find_character_asset

def multiply_base_tint(material, tint, label, property_name):
    if len(tint)!=3 or not all(math.isfinite(v) and v>=0 for v in tint):
        raise FormatError('Invalid native colour multiplier')
    if all(abs(v-1)<=1e-6 for v in tint):return
    nodes,links=material.node_tree.nodes,material.node_tree.links
    base=nodes['Principled BSDF'].inputs['Base Color']
    multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
    multiply.label=label;multiply.inputs[0].default_value=1
    if base.is_linked:links.new(base.links[0].from_socket,multiply.inputs[1])
    else:multiply.inputs[1].default_value=base.default_value
    multiply.inputs[2].default_value=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in tint)+(1,)
    links.new(multiply.outputs[0],base)
    material[property_name]=list(tint)


class CostumeMaterials:
    def __init__(self, assets, suffix, report, provenance=None):
        self.assets, self.suffix, self.report = assets, suffix, report
        self.images = {}
        self.stores = {}
        self.provenance = provenance

    def image(self, path):
        # Cached images must retain the revision actually consumed earlier.
        if path in self.images:return self.images[path]
        data=path.read_bytes()
        if self.provenance:self.provenance.record(path,'texture',data=data)
        return self.dds_image(path, data, path.stem)

    def dds_image(self, key, data, label):
        if key not in self.images:
            try:
                span = read_embedded_dds(data)
            except FormatError as error:
                raise FormatError(f'Native texture {label}: {error}') from error
            # Blender reads DDS itself; pack before discarding the temporary file.
            payload = Path(tempfile.gettempdir())/('tt-texture-'+uuid.uuid4().hex+'.dds')
            try:
                with payload.open('xb') as stream:stream.write(data[span['offset']:span['end']])
                image = bpy.data.images.load(str(payload), check_existing=False)
                image.pack()
            finally:
                payload.unlink(missing_ok=True)
            image.name = label
            self.images[key] = image
        return self.images[key]

    def model_texture(self, model, index):
        source = Path(model['source'])
        path = None
        try:
            relative = source.relative_to(self.assets.root)
        except ValueError:
            # Explicit raw models may live outside the selected asset tree.
            # Keep their companions inside that provider and let its existing
            # unique-basename fallback reject any ambiguous candidates.
            pass
        else:
            path = self.assets.find_exact(relative.with_suffix('.NXG_TEXTURES').as_posix(), required=False)
        if path is None:
            path = self.assets.find(source.stem+'.NXG_TEXTURES')
        if path not in self.stores:
            self.stores[path] = read_texture_store(path)
        store = self.stores[path]
        if self.provenance:self.provenance.record(path,'texture-store',data=store['data'])
        if not 0 <= index < len(store['entries']):
            raise FormatError(f'Texture {index} is outside {path.name}')
        entry = store['entries'][index]
        if 'offset' not in entry:
            raise FormatError(f'Texture {index} in {path.name} is an external/shared slot')
        if entry['kind'] == 3:
            raise FormatError('VTF data cannot be used as surface albedo')
        return path, entry, store['data'][entry['offset']:entry['end']]

    def model_image(self, model, index):
        path, entry, data = self.model_texture(model, index)
        return self.dds_image((path,index), data, path.stem+f' / texture {index}')

    def __call__(self, model, entry, definition, attachment_tint=None):
        material = bpy.data.materials.new(Path(model['source']).stem+' / '+entry['name'])
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        surface = nodes.get('Principled BSDF')
        surface.inputs['Roughness'].default_value = .5
        slot = costume_slot(entry)
        if entry.get('table_version') in (163, 174):
            self.report.append({'material':entry['name'], 'issue':'Older static shader flag meanings remain unresolved; texture/UV and render footer are decoded, shading is approximate'})
        matched_objects = [(i, o) for i, o in enumerate(definition['objects']) if o['fields'].get('Material')==slot] if definition and slot is not None else []
        matched = [o['fields'] for _, o in matched_objects]
        used_fields = {i: {'Material'} for i, _ in matched_objects}
        def used(values, *names):
            for i, obj in matched_objects:
                if obj['fields'] is values:
                    used_fields[i].update(names)
        texture = next((o for o in matched if o.get('Texture Slot')==0 and 'Texture File' in o
                        and active_renderer_reference(o['Texture File'], self.suffix)), None)
        assigned = False
        textured = False
        if texture:
            try:
                path = find_character_asset(self.assets,texture['Texture File'],self.suffix,'.TEX')
                image = self.image(path)
                node = nodes.new('ShaderNodeTexImage');node.image=image
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                links.new(node.outputs['Alpha'], surface.inputs['Alpha'])
                uv_index=costume_uv_index(entry, model['mesh_version'])
                uv = nodes.new('ShaderNodeUVMap');uv.uv_map=f'Source uv {uv_index}'
                links.new(uv.outputs['UV'], node.inputs['Vector'])
                material['tt_costume_uv_index'] = uv_index
                used(texture, 'Texture Slot', 'Texture File')
                assigned = True
                textured = True
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if not assigned:
            tint_fields = next((o for o in matched if 'Layer 1 Tint Colour' in o), None)
            if tint_fields is not None:
                tint = tint_fields['Layer 1 Tint Colour']
                surface.inputs['Base Color'].default_value = tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in tint[:3])+(1,)
                used(tint_fields, 'Layer 1 Tint Colour')
                assigned = True
        if not assigned and entry['texture_ids'][0] >= 0:
            try:
                image = self.model_image(model, entry['texture_ids'][0])
                node = nodes.new('ShaderNodeTexImage');node.image=image
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                if entry['fields']['canAlphaBlend'] or entry['fields'].get('alphaTest') == 5:
                    links.new(node.outputs['Alpha'], surface.inputs['Alpha'])
                uv_index = entry['fields']['uvSets'][0][1]
                if uv_index == 0xffffffff:uv_index = 0
                uv = nodes.new('ShaderNodeUVMap');uv.uv_map=f'Source uv {uv_index}'
                links.new(uv.outputs['UV'], node.inputs['Vector'])
                assigned = textured = True
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if not assigned:
            if entry['fields']['vertAlbedo'] or entry['texture_formats']:
                node = nodes.new('ShaderNodeVertexColor');node.layer_name='SourceColor'
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                assigned = True
                if not entry['fields']['vertAlbedo']:
                    self.report.append({'material':entry['name'], 'issue':'Modern untextured material uses source vertex colors for inspection; shader color flags remain approximate'})
        if not assigned:
            self.report.append({'material':entry['name'], 'issue':'Native material texture store or constant color remains unresolved'})
        if textured:
            attach_vertex_albedo(material, native_vert_albedo=bool(entry['fields']['vertAlbedo']))
        if definition:
            tint = definition['character'].get('Default Tint Colour', (1,1,1))
            multiply_base_tint(material,tint,'Character definition default tint','tt_definition_default_tint')
        if attachment_tint is not None:
            multiply_base_tint(material,attachment_tint,'Character attachment tint','tt_attachment_tint')
        attach_vertex_opacity(material, native_ignore_vertex_opacity=bool(entry['fields']['ignoreVertexOpacity']),
                              native_can_alpha_blend=bool(entry['fields']['canAlphaBlend']))
        if entry['fields'].get('alphaTest') == 5 and surface.inputs['Alpha'].is_linked:
            # Preserve cutouts even when the native material is not blended.
            # Alpha-test reference is stored as an eight-bit footer value.
            alpha = surface.inputs['Alpha']
            threshold = nodes.new('ShaderNodeMath');threshold.operation = 'GREATER_THAN'
            threshold.inputs[1].default_value = entry['render_flags']['aref']/255
            links.new(alpha.links[0].from_socket, threshold.inputs[0])
            links.new(threshold.outputs[0], alpha)
            if hasattr(material, 'surface_render_method'):material.surface_render_method='DITHERED'
            material['tt_native_alpha_reference'] = entry['render_flags']['aref']
        normal = surface_normal_binding(entry, model['mesh_version'])
        normal_applied = False
        if normal:
            try:
                path, texture, data = self.model_texture(model, normal['texture'])
                if texture['kind'] != 1 or texture['dds']['format'] != 'DXT5':
                    raise FormatError('Native surface normal needs the verified embedded DXT5 layout')
                image = self.dds_image((path,normal['texture'],'normal'), data, path.stem+f' / normal {normal["texture"]}')
                normal_applied = attach_normal_map(material, image, packed_x_alpha=normal['packed_x_alpha'],
                                                   uv_map=f'Source uv {normal["uv"]}')
                material['tt_native_normal_source'] = str(path)
                material['tt_native_normal_texture'] = normal['texture']
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        diagnostic = material_capability_report(model, entry, definition,
            used_definition_fields=used_fields, normal_binding=normal, normal_applied=normal_applied)
        if diagnostic:self.report.append(diagnostic)
        material['tt_material_status'] = 'Costume texture/tint or native vertex color; full shader reconstruction incomplete'
        return material
