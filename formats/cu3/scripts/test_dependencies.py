"""Dependency graph checks with synthetic asset trees; no game data required."""
import shutil
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('dependency_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from dependency_fixture.asset_index import AssetIndex
from dependency_fixture.dependencies import ResourceResolver, dependency_report, MissingResource, active_attachments, find_character_asset
from dependency_fixture.cu3 import FormatError


def definition(model, attachments=(), textures=()):
    objects=[{'class':'Character Attachment','fields':{'Layer':layer,'Resource File':ref},'complete':True} for layer,ref in attachments]
    objects += [{'class':'Texture','fields':{'Texture File':ref},'complete':True} for ref in textures]
    return {'character':{'Skeleton Name':model,'Use Default Layers':2,'Default Layers':2},'objects':objects}


class DependencyTests(unittest.TestCase):
    def test_high_attachment_layer_and_empty_custom_slot(self):
        d = definition('Body', [(36, 'Cape'), (1, '')])
        d['character']['Default Layers'] = (1 << 36) | 2
        self.assertEqual([a['Resource File'] for a in active_attachments(d)], ['Cape'])

    def setUp(self):
        self.root=Path(tempfile.gettempdir())/('tt-dependency-test-'+uuid.uuid4().hex)
        self.root.mkdir()
        self.definitions={}
        self.mock=patch('dependency_fixture.dependencies.character_definition',side_effect=lambda p:self.definitions[p.stem.casefold()])
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        assert self.root.resolve().parent==Path(tempfile.gettempdir()).resolve()
        shutil.rmtree(self.root)

    def file(self,name,data=b'fixture'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def resolver(self):return ResourceResolver(AssetIndex(self.root),'LB3')

    def test_character_namespace_model_paths(self):
        self.file('chars/Super_Character/Face/FACE_HERO_DX11.GHG')
        self.file('unrelated/FACE_HERO_DX11.GHG',b'wrong')
        model=self.resolver().resolve_model('Super_Character/Face/FACE_HERO')
        self.assertEqual(model.relative_to(self.root).as_posix(),
                         'chars/Super_Character/Face/FACE_HERO_DX11.GHG')
        self.assertIsNone(self.resolver().resolve_model('Other/Face/FACE_HERO',required=False))

    def test_exact_model_path_precedes_character_namespace(self):
        self.file('Super_Character/Face/FACE_HERO_DX11.GHG',b'exact')
        self.file('chars/Super_Character/Face/FACE_HERO_DX11.GHG',b'namespace')
        self.assertEqual(self.resolver().resolve_model('Super_Character/Face/FACE_HERO').read_bytes(),b'exact')

    def test_character_namespace_definition_paths(self):
        self.file('chars/Minifigs/Hero/Hero.CD')
        self.file('chars/Minifigs/Hero/Body_DX11.GHG')
        self.file('unrelated/Hero.CD',b'wrong')
        self.definitions['hero']=definition('Minifigs/Hero/Body')
        resolved=self.resolver().resolve('Minifigs/Hero/Hero')
        self.assertEqual(resolved['definition_path'].relative_to(self.root).as_posix(),
                         'chars/Minifigs/Hero/Hero.CD')
        self.assertEqual(resolved['model'].name,'Body_DX11.GHG')

    def test_original_marvel_versions_pass_profile_gate_only(self):
        resolver=ResourceResolver(AssetIndex(self.root),'LMSH1')
        for version in (16,17,18):
            resolver.validate_cutscene(types.SimpleNamespace(version=version))
        for version in (15,19,30):
            with self.assertRaises(FormatError):
                resolver.validate_cutscene(types.SimpleNamespace(version=version))
        with self.assertRaises(FormatError):
            self.resolver().validate_cutscene(types.SimpleNamespace(version=18))

    def test_costume_texture_uses_character_namespace_without_basename_fallback(self):
        self.file('chars/Minifigs/Body/PRINT_DX11.TEX',b'correct')
        self.file('other/PRINT_DX11.TEX',b'wrong')
        assets=AssetIndex(self.root)
        self.assertEqual(find_character_asset(assets,'Minifigs/Body/PRINT','_DX11','.TEX').read_bytes(),b'correct')
        with self.assertRaises(MissingResource):
            find_character_asset(assets,'Minifigs/Other/PRINT','_DX11','.TEX')

    def test_exact_configuration_lookup_does_not_fall_back_to_basename(self):
        self.file('CUT/Story/Scene.txt',b'declaration')
        index=AssetIndex(self.root)
        self.assertEqual(index.find_exact('cut/story/scene.TXT').read_bytes(),b'declaration')
        self.assertIsNone(index.find_exact('other/Scene.txt',required=False))
        with self.assertRaises(FormatError):index.find_exact('Scene.txt')

    def cut(self,*names):
        return types.SimpleNamespace(version=19,path=Path('fixture.CU3'),actors=[{'name':n,'parent':None,'records':[{}]} for n in names])

    def test_shared_model_active_layers_cycles_and_missing_texture(self):
        for name in ('Hero.CD','Hat.CD','Shared_DX11.GHG','Hat_DX11.GSC'):self.file(name)
        self.definitions['hero']=definition('Shared',[(1,'Hat'),(2,'Inactive')],['Missing_Print'])
        self.definitions['hat']=definition('Hat',[(1,'Hero')])
        report=dependency_report(self.cut('Instance1_Hero','Instance2_Hero'),self.resolver())
        self.assertEqual(report['resolved_resources'],2)
        self.assertEqual(report['missing_textures'],1)
        self.assertEqual(len(report['resources']),2)
        hero=report['resources'][0]
        self.assertEqual(hero['requested_by'],['Instance1_Hero','Instance2_Hero','Hat'])
        self.assertTrue(hero['model'].endswith('Shared_DX11.GHG'))

    def test_missing_definition_can_redirect_model(self):
        report=dependency_report(self.cut('Instance1_Hero'),self.resolver())
        row=report['resources'][0]
        self.assertEqual(row['status'],'missing')
        self.assertEqual(len(row['candidates']),3)
        self.assertIn('Hero.CD',row['candidates'][0])

    def test_definition_resolves_to_specific_missing_model(self):
        self.file('Hero.CD');self.definitions['hero']=definition('OtherModel')
        with self.assertRaises(MissingResource) as caught:self.resolver().resolve('Hero')
        self.assertEqual(caught.exception.candidates,['OtherModel_DX11.GHG','OtherModel_DX11.GSC'])

    def test_ambiguous_model_is_unresolved_not_missing(self):
        self.file('a/Hero_DX11.GHG',b'one');self.file('b/Hero_DX11.GHG',b'two')
        report=dependency_report(self.cut('Instance1_Hero'),self.resolver())
        self.assertEqual(report['unresolved_resources'],1)
        self.assertEqual(report['missing_resources'],0)
        self.assertIn('Ambiguous',report['resources'][0]['issue'])

    def test_case_and_existing_platform_suffix(self):
        self.file('Chars/HERO_DX11.GHG')
        self.assertEqual(self.resolver().resolve('chars/hero_DX11')['model'].name,'HERO_DX11.GHG')

    def test_unsafe_reference_and_profile_mismatch(self):
        with self.assertRaises(FormatError):self.resolver().resolve('../escape')
        cut=self.cut('Hero');cut.version=30
        with self.assertRaises(FormatError):dependency_report(cut,self.resolver())

    def test_invalid_attachment_layer_rejected(self):
        for layer in (-1,64):
            with self.assertRaises(FormatError):active_attachments(definition('Hero',[(layer,'Hat')]))

    def test_declared_root_replacement_uses_target_definition_without_renaming_actor(self):
        self.file('Visible.CD');self.file('VisibleBody_DX11.GHG')
        self.definitions['visible']=definition('VisibleBody')
        cut=self.cut('Instance1_Original')
        resolver=ResourceResolver(AssetIndex(self.root),'LB3',{'Original':'Visible'})
        report=dependency_report(cut,resolver)
        row=report['resources'][0]
        self.assertEqual(row['reference'],'Visible')
        self.assertTrue(row['definition'].endswith('Visible.CD'))
        self.assertEqual(row['requested_by'],['Instance1_Original'])
        self.assertEqual(cut.actors[0]['name'],'Instance1_Original')

    def test_replacement_matches_exact_root_resource_only(self):
        resolver=ResourceResolver(AssetIndex(self.root),'LB3',{'Original':'Visible'})
        self.assertEqual(resolver.actor_reference('Instance2_original'),'Visible')
        self.assertEqual(resolver.actor_reference('Instance2_OriginalArmoured'),'OriginalArmoured')
        self.assertEqual(resolver.actor_reference('Instance2_SomeOriginal'),'SomeOriginal')

    def test_attachment_resource_with_same_name_is_not_replaced(self):
        for name in ('Visible.CD','Original.CD','VisibleBody_DX11.GHG','Attachment_DX11.GSC'):self.file(name)
        self.definitions['visible']=definition('VisibleBody',[(1,'Original')])
        self.definitions['original']=definition('Attachment')
        resolver=ResourceResolver(AssetIndex(self.root),'LB3',{'Original':'Visible'})
        report=dependency_report(self.cut('Instance1_Original'),resolver)
        self.assertEqual(report['resolved_resources'],2)
        self.assertEqual([r['reference']for r in report['resources']],['Visible','Original'])
        self.assertTrue(report['resources'][1]['model'].endswith('Attachment_DX11.GSC'))

    def test_resolver_rejects_unverified_replacement_chain(self):
        with self.assertRaisesRegex(FormatError,'ordering'):
            ResourceResolver(AssetIndex(self.root),'LB3',{'Original':'Visible','Visible':'Third'})

if __name__=='__main__':unittest.main()
