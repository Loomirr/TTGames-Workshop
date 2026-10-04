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
from dependency_fixture.dependencies import ResourceResolver, dependency_report, MissingResource, active_attachments
from dependency_fixture.cu3 import FormatError


def definition(model, attachments=(), textures=()):
    objects=[{'class':'Character Attachment','fields':{'Layer':layer,'Resource File':ref},'complete':True} for layer,ref in attachments]
    objects += [{'class':'Texture','fields':{'Texture File':ref},'complete':True} for ref in textures]
    return {'character':{'Skeleton Name':model,'Use Default Layers':2,'Default Layers':2},'objects':objects}


class DependencyTests(unittest.TestCase):
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
        for layer in (-1,32):
            with self.assertRaises(FormatError):active_attachments(definition('Hero',[(layer,'Hat')]))

if __name__=='__main__':unittest.main()
