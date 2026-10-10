"""Constructed export-library boundary checks; no game assets required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).parent/'Addon/io_scene_tt_character/fortnite_catalog.py'
spec = importlib.util.spec_from_file_location('fortnite_catalog', SOURCE)
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class ExportCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'Exports').mkdir()
        (self.root/'Models').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, path, values):
        path = self.root/'Exports'/path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values))
        return path

    def test_unreal_reference_removes_export_suffix(self):
        self.assertEqual(catalog.reference({'ObjectPath':'/FigureCosmetics/Figure/Test.3'}), 'FigureCosmetics/Figure/Test')

    def test_plugin_path(self):
        self.assertEqual(catalog.package_path(Path('FortniteGame/Plugins/Juno/Content/Figure/Test.json')), 'Juno/Figure/Test')

    def test_game_path(self):
        self.assertEqual(catalog.package_path(Path('FortniteGame/Content/Athena/Test.json')), 'Game/Athena/Test')

    def test_ambiguous_basename_rejected(self):
        self.asset('A/Test.json', [])
        self.asset('B/Test.json', [])
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            catalog.ExportLibrary(self.root).file('Test','.json')

    def test_explicit_path_does_not_use_basename(self):
        self.asset('A/Test.json', [])
        with self.assertRaisesRegex(ValueError,'Missing'):
            catalog.ExportLibrary(self.root).file('/B/Test.0','.json')

    def test_material_parent_and_override(self):
        self.asset('A/Parent.json',[{'Name':'Parent','Properties':{'ScalarParameterValues':[{'ParameterInfo':{'Name':'Color'},'ParameterValue':2}]}}])
        self.asset('A/Child.json',[{'Name':'Child','Properties':{'Parent':{'ObjectPath':'/A/Parent.0'},'ScalarParameterValues':[{'ParameterInfo':{'Name':'Color'},'ParameterValue':3}]}}])
        self.assertEqual(catalog.ExportLibrary(self.root).material('/A/Child.0')['Color'], 3)

    def test_material_cycle_rejected(self):
        self.asset('A/Test.json',[{'Name':'Test','Properties':{'Parent':{'ObjectPath':'/A/Test.0'}}}])
        with self.assertRaisesRegex(ValueError,'Cyclic'):
            catalog.ExportLibrary(self.root).material('/A/Test.0')

    def test_no_character_specific_name_dependency(self):
        # This checks naming, not mount parsing (covered by test_plugin_path).
        # Keep the fixture short enough for Windows runners with deep TEMP paths.
        self.asset('FigureCosmetics/Figure/Figure_Example/Mutable/Dataless/COI_Figure_Example_Dataless.json',[])
        entries = catalog.ExportLibrary(self.root).catalog()
        self.assertEqual(entries[0]['code'],'Example')
        self.assertEqual(entries[0]['label'],'Example')

    def test_baked_textures_not_catalog_characters(self):
        self.asset('FigureCosmetics/Figure/Figure_Example/Bake/FigureBake_Example_TexColorD.json',[])
        self.assertEqual(catalog.ExportLibrary(self.root).catalog(),[])

    def test_unknown_inventory_rejected(self):
        (self.root/'lego-fortnite-index.json').write_text('{"schema":"unknown"}')
        with self.assertRaisesRegex(ValueError,'Unknown'):
            catalog.ExportLibrary(self.root).catalog()

    def test_installed_discovery_is_not_import_proof(self):
        (self.root/'lego-fortnite-index.json').write_text(json.dumps({'schema':'tt-workshop.lego-fortnite-index.v1','entries':[dict(resource='FigureCosmetics/Figure/Unknown',mode='recipe',code='Unknown',label='Unknown',backend_resource='Source/Unknown.uasset')]}))
        library = catalog.ExportLibrary(self.root)
        self.assertEqual(len(library.catalog()),1)
        with self.assertRaisesRegex(ValueError,'Missing exported companion'):
            library.plan(library.catalog()[0])

    def test_cooked_game_folder_rejected(self):
        with self.assertRaisesRegex(ValueError,'export folder'):
            catalog.ExportLibrary(self.root/'Exports')

    def recipe(self, declared_head='/A/DeclaredFace.0'):
        descriptor = dict(IntParameters=[dict(ParameterName=k, ParameterValueName='Default')
                                        for k in ('Body Selector','Body Material Type')],
            FloatParameters=[dict(ParameterName='arm_'+s+h+' Color',ParameterValue=1) for s in 'lr' for h in 'ul'],
            SkeletalMeshParameters=[dict(ParameterName='Head SKM',ParameterValue={'ObjectPath':'/A/Head.0'})],
            MaterialParameters=[dict(ParameterName='Head Material',ParameterValue={'ObjectPath':declared_head})] if declared_head else [],
            TextureParameters=[])
        ref='FigureCosmetics/Figure/Figure_Example/Mutable/Dataless/COI_Figure_Example_Dataless'
        self.asset(ref+'.json',[dict(Name='COI_Figure_Example_Dataless',Type='CustomizableObjectInstance',Properties={'Descriptor':descriptor})])
        self.asset('A/DeclaredFace.json',[dict(Name='DeclaredFace',Properties={'ScalarParameterValues':[
            dict(ParameterInfo={'Name':'Color Head ID'},ParameterValue=1)]})])
        for name in ('SKM_Figure_Preview','A/Head'):
            p=self.root/'Models'/(name+'.glb');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
        (self.root/'Exports/T_LUT_Default.png').write_bytes(b'fixture')
        return dict(resource=ref,mode='recipe',code='Example',label='Example')

    def test_declared_head_reference_replaces_filename_guess(self):
        entry=self.recipe()
        plan=catalog.ExportLibrary(self.root).plan(entry)
        self.assertEqual(plan['head_material']['Color Head ID'],1)

    def test_missing_head_declaration_is_not_guessed(self):
        entry=self.recipe(None)
        with self.assertRaisesRegex(ValueError,'no declared Head Material'):
            catalog.ExportLibrary(self.root).plan(entry)

    def test_missing_companion_can_be_retried(self):
        entry=self.recipe()
        (self.root/'Models/A/Head.glb').unlink()
        with self.assertRaises(catalog.MissingExport):
            catalog.ExportLibrary(self.root).plan(entry)

    def test_duplicate_mounts_do_not_duplicate_browser_entries(self):
        value=dict(resource='FigureCosmetics/Figure/Test',mode='recipe',code='Test',label='Test',backend_resource='Source/Test.uasset')
        (self.root/'lego-fortnite-index.json').write_text(json.dumps({'schema':'tt-workshop.lego-fortnite-index.v1',
            'entries':[value,dict(value,resource=value['resource'].upper())]}))
        self.assertEqual(len(catalog.ExportLibrary(self.root).catalog()),1)

    def test_conflicting_inventory_entries_rejected(self):
        value=dict(resource='FigureCosmetics/Figure/Test',mode='recipe',code='Test',label='Test',backend_resource='Source/Test.uasset')
        (self.root/'lego-fortnite-index.json').write_text(json.dumps({'schema':'tt-workshop.lego-fortnite-index.v1',
            'entries':[value,dict(value,mode='baked')]}))
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            catalog.ExportLibrary(self.root).catalog()

    def test_declared_head_color_overrides_standard_selector(self):
        descriptor={'IntParameters':[dict(ParameterName='Head Standard Color',ParameterValueName='ColorID_24_Bright_yellow')]}
        self.assertEqual(catalog.head_color(descriptor,{'Color Head ID':283},'/A/SpecialHead.0'),283)

    def test_standard_head_selector_color(self):
        descriptor={'IntParameters':[dict(ParameterName='Head Standard Color',ParameterValueName='ColorID_24_Bright_yellow')]}
        mesh='/FigureCharacter/Figure_Core/SkeletalMesh/SKM_Figure_HeadStandard_Mutable.1'
        self.assertEqual(catalog.head_color(descriptor,{},mesh),24)

    def test_standard_selector_does_not_guess_custom_head_colors(self):
        descriptor={'IntParameters':[dict(ParameterName='Head Standard Color',ParameterValueName='ColorID_24_Bright_yellow')]}
        with self.assertRaisesRegex(ValueError,'no color ID'):
            catalog.head_color(descriptor,{},'/A/SpecialHead.0')


if __name__ == '__main__':
    unittest.main()
