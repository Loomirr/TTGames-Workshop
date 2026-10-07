"""Portable diagnostics tests; native shader values remain uninterpreted."""
import copy
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('material_capability_fixture')
package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from material_capability_fixture.material_capabilities import material_capability_report
from material_capability_fixture.native_materials import surface_normal_binding
sys.modules.setdefault('bpy', types.ModuleType('bpy'))
from material_capability_fixture import costume_materials
from material_capability_fixture.asset_index import AssetIndex
from material_capability_fixture.cu3 import FormatError


def fixture():
    entry = dict(index=0, name='BODY_GAME', table_version=176,
        render_flags={'special_id': 3}, texture_ids=[-1] * 18,
        fields=dict(surfaceMapMethod=0, surfaceMapFormat0=0,
                    uvSets=[(0, 0xffffffff)] * 16, glow=0, metallicSpecular=0))
    return dict(source='synthetic.GHG', mesh_version=169, materials=[entry]), entry


def definition(*objects):
    return dict(source='synthetic.CD', character={}, objects=[dict({'offset': 100 + i * 50,
        'complete': True, 'decoded_end': 140 + i * 50}, **obj) for i, obj in enumerate(objects)])


class MaterialCapabilityTests(unittest.TestCase):
    def test_absent_controls_are_not_reported_as_missing_materials(self):
        model, entry = fixture()
        self.assertIsNone(material_capability_report(model, entry))
        # An encoding enum alone does not declare that a texture is used.
        entry['fields']['surfaceMapFormat0'] = 5
        self.assertIsNone(material_capability_report(model, entry))

    def test_successful_texture_fields_and_unused_remap_are_distinct(self):
        model, entry = fixture()
        cd = definition(
            dict({'class': 'Texture Replacement'}, fields={'Material': 3, 'Texture Slot': 0, 'Texture File': 'Print'}),
            dict({'class': 'Material Remap'}, fields={'Material': 3, 'Layer 1 Tint Colour': (0.2, 0.3, 0.4),
                                                      'Native Selector': 77}))
        originals = copy.deepcopy((model, cd))
        report = material_capability_report(model, entry, cd,
            used_definition_fields={0: {'Material', 'Texture Slot', 'Texture File'}, 1: {'Material'}})
        self.assertEqual(report['definition_declarations'][0]['unapplied_fields'], [])
        remap = report['definition_declarations'][1]
        self.assertEqual(remap['unapplied_fields'], ['Layer 1 Tint Colour', 'Native Selector'])
        self.assertEqual(remap['decoded_fields']['Native Selector'], 77)
        self.assertEqual((model, cd), originals)
        remap['decoded_fields']['Native Selector'] = 99
        self.assertEqual(cd['objects'][1]['fields']['Native Selector'], 77)

    def test_successfully_used_tint_is_not_an_omission(self):
        model, entry = fixture()
        cd = definition(dict({'class': 'Material Remap'}, fields={'Material': 3, 'Layer 1 Tint Colour': (1, 0, 0)}))
        self.assertIsNone(material_capability_report(model, entry, cd,
            used_definition_fields={0: {'Material', 'Layer 1 Tint Colour'}}))

    def test_failed_texture_fields_remain_unapplied(self):
        model, entry = fixture()
        cd = definition(dict({'class': 'Texture Replacement'}, fields={'Material': 3, 'Texture Slot': 0, 'Texture File': 'Missing'}))
        report = material_capability_report(model, entry, cd, used_definition_fields={0: {'Material'}})
        self.assertEqual(report['definition_declarations'][0]['unapplied_fields'], ['Texture File', 'Texture Slot'])

    def test_unscoped_and_unknown_role_remaps_are_inventory_not_guessed_bindings(self):
        model, entry = fixture()
        other = copy.deepcopy(entry);other['render_flags']['special_id'] = 5
        model['materials'].append(other)
        cd = definition(
            dict({'class': 'Material Remap'}, fields={'Shader': 'Unknown'}),
            dict({'class': 'Material Remap'}, fields={'Material': 91, 'Opaque Mode': 2}),
            dict({'class': 'Material Remap'}, fields={'Material': 5, 'Opaque Mode': 9}),
            dict({'class': 'Character Attachment'}, fields={'Resource File': 'Hat'}))
        report = material_capability_report(model, entry, cd)
        self.assertEqual([r['object_index'] for r in report['unresolved_material_remaps']], [0, 1])
        self.assertEqual(report['definition_declarations'], [])
        self.assertEqual(report['unresolved_material_remaps'][0]['decoded_fields'], {'Shader': 'Unknown'})

    def test_partial_definition_retains_extent_and_does_not_claim_complete_support(self):
        model, entry = fixture()
        cd = definition(dict({'class': 'Material Remap'}, fields={'Material': 3}, complete=False, decoded_end=117))
        report = material_capability_report(model, entry, cd, used_definition_fields={0: {'Material'}})
        self.assertIn('undecoded tail', report['issue'])
        self.assertEqual(report['definition_declarations'][0]['decoded_end'], 117)

    def test_shader_enums_retained_without_node_values_or_new_format_support(self):
        model, entry = fixture()
        entry['fields'].update(substanceMode=123, roughnessMode=7, glow=1, metallicSpecular=1)
        report = material_capability_report(model, entry)
        self.assertEqual(report['untranslated_shader_controls']['substanceMode'], 123)
        self.assertIn('glow', report['nonzero_untranslated_shader_controls'])
        self.assertIn('metallicSpecular', report['nonzero_untranslated_shader_controls'])
        self.assertNotIn('metallic', report)
        self.assertNotIn('emission_strength', report)

    def test_unknown_surface_encoding_retains_raw_selectors(self):
        model, entry = fixture()
        entry['fields'].update(surfaceMapMethod=1, surfaceMapFormat0=3)
        entry['fields']['uvSets'][4] = (1, 2)
        entry['texture_ids'][6] = 4
        self.assertIsNone(surface_normal_binding(entry, model['mesh_version']))
        report = material_capability_report(model, entry)
        self.assertEqual(report['surface_map']['status'], 'unbound_declaration')
        self.assertEqual(report['surface_map']['decoded_fields']['surfaceMapFormat0'], 3)
        self.assertEqual(report['surface_map']['texture_slot_6'], 4)
        self.assertEqual(report['surface_map']['uv_pair_4'], (1, 2))
        self.assertIsNone(report['surface_map']['verified_normal_binding'])

    def test_verified_normal_application_failure_is_not_an_encoding_guess(self):
        model, entry = fixture()
        entry['fields'].update(surfaceMapMethod=1, surfaceMapFormat0=5)
        entry['fields']['uvSets'][4] = (1, 0)
        entry['texture_ids'][6] = 2
        binding = surface_normal_binding(entry, model['mesh_version'])
        self.assertIsNone(material_capability_report(model, entry, normal_binding=binding, normal_applied=True))
        report = material_capability_report(model, entry, normal_binding=binding)
        self.assertEqual(report['surface_map']['status'], 'verified_binding_not_applied')
        self.assertEqual(report['surface_map']['verified_normal_binding'], binding)


class Socket:
    def __init__(self):
        self.default_value = (0.8, 0.8, 0.8, 1)
        self.is_linked = False
        self.links = []


class Node:
    def __init__(self):
        self.inputs = {name: Socket() for name in ('Base Color', 'Alpha', 'Roughness', 'Vector')}
        self.outputs = {name: Socket() for name in ('Color', 'Alpha', 'UV')}


class Nodes(dict):
    def __init__(self):super().__init__({'Principled BSDF': Node()})
    def new(self, _kind):return Node()


class Material(dict):
    def __init__(self):
        self.node_tree = types.SimpleNamespace(nodes=Nodes(), links=types.SimpleNamespace(new=Mock()))


class MaterialConstructionTests(unittest.TestCase):
    """Real constructor decisions, with only the Blender sockets stubbed."""
    def build(self, cd, *, texture_failure=False, normal_failure=False):
        model, entry = fixture()
        entry['fields'].update(vertAlbedo=0, ignoreVertexOpacity=1, canAlphaBlend=0)
        entry['texture_formats'] = []
        if normal_failure:
            entry['fields'].update(surfaceMapMethod=1, surfaceMapFormat0=5)
            entry['fields']['uvSets'][4] = (1, 0)
            entry['texture_ids'][6] = 2
        assets = types.SimpleNamespace(find=Mock(return_value=Path('Print.TEX')))
        report = []
        factory = costume_materials.CostumeMaterials(assets, '_NXG', report)
        factory.image = Mock(side_effect=OSError('missing texture') if texture_failure else None,
                             return_value=object())
        factory.model_texture = Mock(side_effect=OSError('missing normal'))
        material = Material()
        with patch.object(costume_materials.bpy, 'data', types.SimpleNamespace(
                materials=types.SimpleNamespace(new=Mock(return_value=material))), create=True), \
                patch.object(costume_materials, 'attach_vertex_albedo'), \
                patch.object(costume_materials, 'attach_vertex_opacity'):
            result = factory(model, entry, cd)
        self.assertIs(result, material)
        return material, report

    def test_textured_constructor_records_unapplied_tint_and_remap_controls(self):
        cd = definition(
            dict({'class': 'Texture Replacement'}, fields={'Material': 3, 'Texture Slot': 0, 'Texture File': 'Print'}),
            dict({'class': 'Material Remap'}, fields={'Material': 3, 'Layer 1 Tint Colour': (0.4, 0.4, 0.4), 'Opaque Mode': 7}))
        material, report = self.build(cd)
        diagnostic = next(row for row in report if row.get('kind') == 'material_capabilities')
        self.assertEqual(diagnostic['definition_declarations'][0]['unapplied_fields'], [])
        self.assertEqual(diagnostic['definition_declarations'][1]['unapplied_fields'], ['Layer 1 Tint Colour', 'Opaque Mode'])
        self.assertEqual(material['tt_costume_uv_index'], 1)

    def test_constructor_reports_failed_texture_separately_from_successful_fallback_tint(self):
        cd = definition(
            dict({'class': 'Texture Replacement'}, fields={'Material': 3, 'Texture Slot': 0, 'Texture File': 'Print'}),
            dict({'class': 'Material Remap'}, fields={'Material': 3, 'Layer 1 Tint Colour': (1, 0, 0)}))
        material, report = self.build(cd, texture_failure=True)
        self.assertEqual(report[0]['issue'], 'missing texture')
        diagnostic = next(row for row in report if row.get('kind') == 'material_capabilities')
        self.assertEqual(diagnostic['definition_declarations'][0]['unapplied_fields'], ['Texture File', 'Texture Slot'])
        self.assertEqual(diagnostic['definition_declarations'][1]['unapplied_fields'], [])
        self.assertEqual(material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value, (1, 0, 0, 1))

    def test_constructor_reports_verified_normal_load_failure_without_changing_gate(self):
        cd = definition(dict({'class': 'Material Remap'}, fields={'Material': 3, 'Layer 1 Tint Colour': (1, 0, 0)}))
        _, report = self.build(cd, normal_failure=True)
        self.assertEqual(report[0]['issue'], 'missing normal')
        self.assertEqual(report[1]['surface_map']['status'], 'verified_binding_not_applied')


class MaterialCompanionLookupTests(unittest.TestCase):
    """Use real provider lookup and bounded TXTS/DDS decoding, with no game assets."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets_root = self.root / 'selected-assets'
        self.assets_root.mkdir()
        self.external = self.root / 'separate-models' / 'body_nxg.ghg'
        self.external.parent.mkdir()
        self.external.write_bytes(b'Synthetic explicit model; this check does not decode geometry')

    def store(self, folder, byte=0):
        name = b'normal\0'
        data = b'TSXT'+bytes(4)+b'TSXT'+struct.pack('>I',1)+bytes(4)+b'ROTV'+struct.pack('>I',1)
        data += bytes(16)+struct.pack('>I',len(name))+name+struct.pack('>I',1<<8)
        dds = bytearray(128);dds[:4]=b'DDS '
        struct.pack_into('<7I',dds,4,124,0x1007,4,4,0,0,1)
        struct.pack_into('<2I',dds,76,32,4);dds[84:88]=b'DXT5'
        struct.pack_into('<I',dds,108,0x1000)
        payload = bytes(dds)+bytes([byte])*16
        path = self.assets_root / folder / 'body_nxg.NXG_TEXTURES'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data+payload)
        return path, payload

    def factory(self):
        return costume_materials.CostumeMaterials(AssetIndex(self.assets_root),'_NXG',[])

    def test_outside_root_model_uses_existing_unique_provider_fallback(self):
        path,payload = self.store('textures')
        factory = self.factory()
        resolved,entry,data = factory.model_texture({'source':str(self.external)},0)
        self.assertEqual((resolved,entry['kind'],entry['dds']['format'],data),(path,1,'DXT5',payload))
        self.assertEqual(factory.report,[])

    def test_in_root_exact_companion_wins_over_other_identical_basenames(self):
        path,payload = self.store('characters/a',17)
        self.store('characters/b',29)
        source = path.with_suffix('.ghg');source.write_bytes(b'Synthetic sibling model')
        resolved,_,data = self.factory().model_texture({'source':str(source)},0)
        self.assertEqual((resolved,data),(path,payload))

    def test_unqualified_fallback_still_rejects_ambiguous_companions(self):
        self.store('characters/a');self.store('characters/b')
        with self.assertRaisesRegex(FormatError,'Ambiguous asset reference'):
            self.factory().model_texture({'source':str(self.external)},0)

    def test_missing_provider_companion_does_not_probe_beside_external_model(self):
        path,_ = self.store('temporary')
        outside = self.external.with_suffix('.NXG_TEXTURES')
        outside.write_bytes(path.read_bytes());path.unlink()
        with self.assertRaisesRegex(FormatError,'Missing asset'):
            self.factory().model_texture({'source':str(self.external)},0)

    def build(self, factory):
        model,entry = fixture();model['source']=str(self.external)
        entry['fields'].update(vertAlbedo=0,ignoreVertexOpacity=1,canAlphaBlend=0,
                              surfaceMapMethod=1,surfaceMapFormat0=5)
        entry['fields']['uvSets'][0]=entry['fields']['uvSets'][4]=(1,0)
        entry['texture_formats']=[];entry['texture_ids'][0]=entry['texture_ids'][6]=0
        factory.dds_image=Mock(return_value=object())
        material=Material()
        with patch.object(costume_materials.bpy,'data',types.SimpleNamespace(
                materials=types.SimpleNamespace(new=Mock(return_value=material))),create=True), \
                patch.object(costume_materials,'attach_vertex_albedo'), \
                patch.object(costume_materials,'attach_vertex_opacity'), \
                patch.object(costume_materials,'attach_normal_map',return_value=True) as normal:
            factory(model,entry,None)
        return material,normal

    def test_constructor_uses_outside_root_fallback_for_albedo_and_verified_normal(self):
        path,payload=self.store('textures')
        before=path.read_bytes();factory=self.factory()
        material,normal=self.build(factory)
        self.assertEqual(factory.dds_image.call_count,2)
        self.assertTrue(all(call.args[1]==payload for call in factory.dds_image.call_args_list))
        normal.assert_called_once()
        self.assertEqual(material['tt_native_normal_source'],str(path))
        self.assertEqual(factory.report,[])
        self.assertEqual(path.read_bytes(),before)

    def test_constructor_reports_missing_normal_and_albedo_with_provider_error(self):
        factory=self.factory();material,normal=self.build(factory)
        normal.assert_not_called();factory.dds_image.assert_not_called()
        self.assertEqual(sum('Missing asset: body_nxg.NXG_TEXTURES' in row.get('issue','')
                             for row in factory.report),2)
        report=next(row for row in factory.report if row.get('kind')=='material_capabilities')
        self.assertEqual(report['surface_map']['status'],'verified_binding_not_applied')
        self.assertNotIn('tt_native_normal_source',material)


if __name__ == '__main__':
    unittest.main()
