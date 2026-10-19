"""Character-definition costume slots, using the user's native TEX files."""
import tempfile
import uuid
import math
from pathlib import Path
import bpy
from .cu3 import FormatError
from .material_preview import attach_vertex_albedo, attach_vertex_opacity, attach_normal_map, attach_albedo_glow, cubemap_to_equirect, attach_reflection_cubemap
from .texture_store import read_texture_store, read_embedded_texture_store
from .dds import read_embedded_dds
from .native_materials import costume_slot, costume_uv_index, surface_normal_binding, reflection_cubemap_binding, read_materials_bytes
from .profiles import active_renderer_reference
from .material_capabilities import material_capability_report
from .dependencies import find_character_asset
from .material_remaps import shared_glow_binding, native_vertex_glow

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
        self.remap_tables = {}
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

    def reflection_image(self, model, index, label):
        """Resample a native cubemap into one equirectangular image (cached)."""
        import numpy as np
        path, texture, data = self.model_texture(model, index)
        key = (path, index, 'reflection')
        if key in self.images:
            return self.images[key]
        span = read_embedded_dds(data)
        if span['face_count'] != 6 or span['header_bytes'] != 128 or span['array_size'] != 1:
            raise FormatError('Reflection binding needs a six-face legacy DDS cubemap')
        header = bytearray(data[span['offset']:span['offset']+128])
        header[28:32] = (1).to_bytes(4, 'little')            # one mip
        header[108:112] = (0x1000).to_bytes(4, 'little')     # plain texture
        header[112:116] = bytes(4)                           # not a cubemap
        flags = int.from_bytes(header[8:12], 'little') & ~0x20000
        header[8:12] = flags.to_bytes(4, 'little')
        chain = sum(level['bytes'] for level in span['levels'])
        faces = []
        for face in range(6):
            start = span['payload_offset'] + face*chain
            payload = Path(tempfile.gettempdir())/('tt-face-'+uuid.uuid4().hex+'.dds')
            try:
                with payload.open('xb') as stream:
                    stream.write(bytes(header) + data[start:start+span['levels'][0]['bytes']])
                face_image = bpy.data.images.load(str(payload), check_existing=False)
                width, height = face_image.size
                pixels = np.empty(width*height*4, dtype=np.float32)
                face_image.pixels.foreach_get(pixels)
                bpy.data.images.remove(face_image)
            finally:
                payload.unlink(missing_ok=True)
            faces.append(pixels.reshape(height, width, 4)[::-1])
        equirect = cubemap_to_equirect(faces)
        image = bpy.data.images.new(label, equirect.shape[1], equirect.shape[0], alpha=False)
        image.pixels.foreach_set(equirect.ravel())
        image.pack()
        self.images[key] = image
        return image

    def model_texture(self, model, index):
        source = Path(model['source'])
        if model.get('mesh_version') == 48:
            # LEGO Batman 2 keeps the textures inside the model itself.
            if source not in self.stores:
                self.stores[source] = read_embedded_texture_store(source)
            store = self.stores[source]
            if self.provenance:self.provenance.record(source,'texture-store',data=store['data'])
            if not 0 <= index < len(store['entries']):
                raise FormatError(f'Texture {index} is outside {source.name}')
            entry = store['entries'][index]
            if 'offset' not in entry:
                raise FormatError(f'Texture {index} in {source.name} has no image')
            return source, entry, store['data'][entry['offset']:entry['end']]
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

    def remap_glow(self, material, model, matched_objects, used_fields):
        declarations = [(i, o['fields']) for i, o in matched_objects
                        if o['fields'].get('Source Material Type') == 1
                        and o['fields'].get('Source Material Resource File')
                        and o['fields'].get('Source Material')]
        if not declarations or model['mesh_version'] != 169:return
        if len(declarations) != 1:
            raise FormatError('Multiple replacement-material declarations match this costume role')
        index, fields = declarations[0]
        path = find_character_asset(self.assets, fields['Source Material Resource File'], self.suffix, '.GSC')
        if path not in self.remap_tables:
            with path.open('rb') as stream:
                data = stream.read(256*1024*1024+1)
            if len(data) > 256*1024*1024:
                raise FormatError('Replacement-material resource exceeds the supported byte limit')
            self.remap_tables[path] = (read_materials_bytes(data), data)
        table, data = self.remap_tables[path]
        binding = shared_glow_binding(table['materials'], fields['Source Material'], model['mesh_version'])
        if binding is None:return
        if self.provenance:self.provenance.record(path, 'material-remap', data=data)
        resource = dict(source=str(path))
        store, texture, payload = self.model_texture(resource, binding['texture'])
        if texture['kind'] != 0:
            raise FormatError('Replacement glow requires an ordinary color texture')
        image = self.dds_image((store,binding['texture'],'glow'), payload, path.stem+' / additive glow')
        tree=material.node_tree;surface=tree.nodes.get('Principled BSDF')
        node=tree.nodes.new('ShaderNodeTexImage');node.image=image;node.label='Native replacement additive layer'
        uv=tree.nodes.new('ShaderNodeUVMap');uv.uv_map=f'Source uv {binding["uv"]}'
        tree.links.new(uv.outputs['UV'],node.inputs['Vector'])
        tree.links.new(node.outputs['Color'],surface.inputs['Emission Color'])
        surface.inputs['Emission Strength'].default_value=1
        used_fields[index].update(('Source Material Type','Source Material Resource File','Source Material'))
        material['tt_remap_glow_source']=str(path)
        material['tt_remap_glow_texture']=binding['texture']
        material['tt_remap_glow_uv']=binding['uv']
        material['tt_remap_glow_preview']='Common additive mask; unit preview intensity, native exposure/intensity unverified'
        self.report.append(dict(kind='material_remap_glow',material=material.name,source=str(path),
            declaration_index=index,binding=binding,
            issue='Additive mask reconstructed at unit preview intensity; replacement BRDF/metallic shader remains incomplete'))

    def __call__(self, model, entry, definition, attachment_tint=None):
        material = bpy.data.materials.new(Path(model['source']).stem+' / '+entry['name'])
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        surface = nodes.get('Principled BSDF')
        surface.inputs['Roughness'].default_value = .5
        if entry.get('table_version') in (168, 169) and entry['fields']['shaderType'] == 15:
            # Inspection approximation for the older glass pass. This keeps
            # the screen behind it visible; it is not the native refraction.
            surface.inputs['Alpha'].default_value = .12
            material['tt_preview_glass_approximation'] = True
            self.report.append({'material':entry['name'], 'issue':'Older glass shader uses a transparent preview; native refraction remains unresolved'})
        slot = costume_slot(entry)
        if entry.get('table_version') in (163, 166, 168, 169, 172, 174):
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
                # LEGO Batman 2 parts carry one UV pair; its shader prefix is opaque.
                uv_index = 0 if model['mesh_version'] == 48 else entry['fields']['uvSets'][0][1]
                if uv_index == 0xffffffff:uv_index = 0
                uv = nodes.new('ShaderNodeUVMap');uv.uv_map=f'Source uv {uv_index}'
                links.new(uv.outputs['UV'], node.inputs['Vector'])
                assigned = textured = True
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if not assigned:
            reflection = reflection_cubemap_binding(entry, model['mesh_version'])
            if reflection:
                try:
                    image = self.reflection_image(model, reflection['texture'],
                                                  Path(model['source']).stem+f' / reflection {reflection["texture"]}')
                    assigned = attach_reflection_cubemap(material, image)
                except (ValueError, RuntimeError, OSError) as error:
                    self.report.append({'material':entry['name'], 'issue':'Reflection cubemap: '+str(error)})
        if not assigned:
            # Earlier attachment shaders expose authored vertex colors but
            # their albedo flags are not decoded. For the observed untextured
            # MESH169/UMTL174 layout, retain those colors in the inspection
            # preview instead of replacing them with Blender's default white.
            # This does not resolve missing atlas textures or native shading.
            older_vertex_preview = (
                (model['mesh_version'],entry.get('table_version')) == (169,174)
                and entry['fields']['vertAlbedo'] is None and entry['texture_ids'][0] < 0
                and bool(model.get('parts')) and all(
                    p.get('vertices') and 'color' in p['vertices'][0] for p in model['parts']))
            if entry['fields']['vertAlbedo'] or entry['texture_formats'] or older_vertex_preview:
                node = nodes.new('ShaderNodeVertexColor');node.layer_name='SourceColor'
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                assigned = True
                if older_vertex_preview:
                    material['tt_preview_vertex_color_fallback'] = True
                    self.report.append({'material':entry['name'], 'issue':'Older untextured material uses authored vertex colors for inspection; native albedo flags and lighting remain unresolved'})
                elif not entry['fields']['vertAlbedo']:
                    self.report.append({'material':entry['name'], 'issue':'Modern untextured material uses source vertex colors for inspection; shader color flags remain approximate'})
        if (not assigned and model['mesh_version'] == 48 and entry['texture_ids'][0] < 0
                and model.get('parts') and all(p.get('vertices') and 'color' in p['vertices'][0] for p in model['parts'])):
            # LEGO Batman 2 colours untextured faces, cowls and hair with
            # vertex colours stored at half strength: white details peak at
            # 127. Double them (about 2**2.2 in linear light) for inspection;
            # the source colour attribute itself is left unchanged.
            node = nodes.new('ShaderNodeVertexColor');node.layer_name='SourceColor'
            double = nodes.new('ShaderNodeMixRGB');double.blend_type='MULTIPLY';double.use_clamp=True
            double.label='LB2 half-strength vertex colour';double.inputs[0].default_value=1
            double.inputs[2].default_value=(2**2.2,2**2.2,2**2.2,1)
            links.new(node.outputs['Color'], double.inputs[1])
            links.new(double.outputs[0], surface.inputs['Base Color'])
            material['tt_lb2_vertex_colour_scale'] = 2
            assigned = True
            self.report.append({'material':entry['name'], 'issue':'LB2 untextured material uses doubled source vertex colors for inspection (approximate)'})
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
                expected = 'DXT5' if normal['packed_x_alpha'] else 'DXT1'
                if texture['kind'] != 1 or texture['dds']['format'] != expected:
                    raise FormatError(f'Native surface normal needs the verified embedded {expected} layout')
                image = self.dds_image((path,normal['texture'],'normal'), data, path.stem+f' / normal {normal["texture"]}')
                normal_applied = attach_normal_map(material, image, packed_x_alpha=normal['packed_x_alpha'],
                                                   uv_map=f'Source uv {normal["uv"]}')
                material['tt_native_normal_source'] = str(path)
                material['tt_native_normal_texture'] = normal['texture']
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if native_vertex_glow(entry, model['mesh_version']):
            attach_albedo_glow(material)
        try:self.remap_glow(material, model, matched_objects, used_fields)
        except (ValueError, RuntimeError, OSError) as error:
            self.report.append({'material':entry['name'], 'issue':'Replacement material: '+str(error)})
        diagnostic = material_capability_report(model, entry, definition,
            used_definition_fields=used_fields, normal_binding=normal, normal_applied=normal_applied)
        if diagnostic:self.report.append(diagnostic)
        material['tt_material_status'] = 'Costume texture/tint or native vertex color; full shader reconstruction incomplete'
        return material
