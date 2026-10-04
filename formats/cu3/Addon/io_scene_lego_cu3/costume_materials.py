"""Character-definition costume slots, using the user's native TEX files."""
import tempfile
import uuid
from pathlib import Path
import bpy
from .cu3 import FormatError
from .material_preview import attach_vertex_albedo, attach_vertex_opacity
from .texture_store import read_texture_store

SLOTS = {'headfrontgame':1, 'headbackgame':2, 'bodyfrontgame':3, 'bodybackgame':4,
         'hipsgame':5, 'lefthandgame':6, 'leftarmgame':7, 'leftleggame':8,
         'rightarmgame':24, 'rightleggame':25, 'righthandgame':26}


class CostumeMaterials:
    def __init__(self, assets, suffix, report):
        self.assets, self.suffix, self.report = assets, suffix, report
        self.images = {}
        self.stores = {}

    def image(self, path):
        return self.dds_image(path, path.read_bytes(), path.stem)

    def dds_image(self, key, data, label):
        if key not in self.images:
            at = data.find(b'DDS ')
            if at < 0 or at+128 > len(data) or int.from_bytes(data[at+4:at+8],'little') != 124:
                raise FormatError(f'Native texture has no supported DDS payload: {label}')
            # Blender reads DDS itself; pack before discarding the temporary file.
            payload = Path(tempfile.gettempdir())/('tt-texture-'+uuid.uuid4().hex+'.dds')
            try:
                with payload.open('xb') as stream:stream.write(data[at:])
                image = bpy.data.images.load(str(payload), check_existing=False)
                image.pack()
            finally:
                payload.unlink(missing_ok=True)
            image.name = label
            self.images[key] = image
        return self.images[key]

    def model_image(self, model, index):
        path = self.assets.find(Path(model['source']).stem+'.NXG_TEXTURES')
        if path not in self.stores:
            self.stores[path] = read_texture_store(path)
        store = self.stores[path]
        if not 0 <= index < len(store['entries']):
            raise FormatError(f'Texture {index} is outside {path.name}')
        entry = store['entries'][index]
        if 'offset' not in entry:
            raise FormatError(f'Texture {index} in {path.name} is an external/shared slot')
        if entry['kind'] == 3:
            raise FormatError('VTF data cannot be used as surface albedo')
        return self.dds_image((path,index), store['data'][entry['offset']:entry['end']],
                              path.stem+f' / texture {index}')

    def __call__(self, model, entry, definition):
        material = bpy.data.materials.new(Path(model['source']).stem+' / '+entry['name'])
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        surface = nodes.get('Principled BSDF')
        surface.inputs['Roughness'].default_value = .5
        key = entry['name'].replace('_','').split(':')[0].casefold()
        slot = SLOTS.get(key)
        matched = [o['fields'] for o in definition['objects'] if o['fields'].get('Material')==slot] if definition and slot is not None else []
        texture = next((o for o in matched if o.get('Texture Slot')==0 and 'Texture File' in o), None)
        assigned = False
        textured = False
        if texture:
            try:
                path = self.assets.find(texture['Texture File'], self.suffix, '.TEX')
                image = self.image(path)
                node = nodes.new('ShaderNodeTexImage');node.image=image
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                links.new(node.outputs['Alpha'], surface.inputs['Alpha'])
                uv = nodes.new('ShaderNodeUVMap');uv.uv_map='Source uv 1'
                links.new(uv.outputs['UV'], node.inputs['Vector'])
                assigned = True
                textured = True
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if not assigned:
            tint = next((o['Layer 1 Tint Colour'] for o in matched if 'Layer 1 Tint Colour' in o), None)
            if tint is not None:
                surface.inputs['Base Color'].default_value = tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in tint[:3])+(1,)
                assigned = True
        if not assigned and entry['texture_ids'][0] >= 0:
            try:
                image = self.model_image(model, entry['texture_ids'][0])
                node = nodes.new('ShaderNodeTexImage');node.image=image
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                if entry['fields']['canAlphaBlend']:
                    links.new(node.outputs['Alpha'], surface.inputs['Alpha'])
                uv_index = entry['fields']['uvSets'][0][1]
                if uv_index == 0xffffffff:uv_index = 0
                uv = nodes.new('ShaderNodeUVMap');uv.uv_map=f'Source uv {uv_index}'
                links.new(uv.outputs['UV'], node.inputs['Vector'])
                assigned = textured = True
            except (ValueError, RuntimeError, OSError) as error:
                self.report.append({'material':entry['name'], 'issue':str(error)})
        if not assigned:
            if entry['fields']['vertAlbedo']:
                node = nodes.new('ShaderNodeVertexColor');node.layer_name='SourceColor'
                links.new(node.outputs['Color'], surface.inputs['Base Color'])
                assigned = True
        if not assigned:
            self.report.append({'material':entry['name'], 'issue':'Native material texture store or constant color remains unresolved'})
        if textured:
            attach_vertex_albedo(material, native_vert_albedo=bool(entry['fields']['vertAlbedo']))
        if definition:
            tint = definition['character'].get('Default Tint Colour', (1,1,1))
            if any(abs(v-1)>1e-6 for v in tint):
                base = surface.inputs['Base Color']
                multiply = nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
                multiply.label='Character definition default tint';multiply.inputs[0].default_value=1
                if base.is_linked:links.new(base.links[0].from_socket,multiply.inputs[1])
                else:multiply.inputs[1].default_value=base.default_value
                multiply.inputs[2].default_value=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in tint)+(1,)
                links.new(multiply.outputs[0],base)
                material['tt_definition_default_tint']=list(tint)
        attach_vertex_opacity(material, native_ignore_vertex_opacity=bool(entry['fields']['ignoreVertexOpacity']),
                              native_can_alpha_blend=bool(entry['fields']['canAlphaBlend']))
        material['tt_material_status'] = 'Costume texture/tint or native vertex color; full shader reconstruction incomplete'
        return material
