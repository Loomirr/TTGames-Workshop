"""Refusal and common-binding checks; original visual evidence stays local."""
import copy
import sys
import types
import unittest
from pathlib import Path

package=types.ModuleType('remap_tests')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from remap_tests.material_remaps import shared_glow_binding, native_vertex_glow
from remap_tests.cu3 import FormatError


def entry():
    return dict(name='DeclaredGlow',table_version=176,texture_ids=[3,6]+[-1]*16,
        fields=dict(version=2,shaderVersion=4,glow=1,shadedGlow=0,
                    layerBlendDiffuse0=2,layerBlendDiffuse1=0,uvSets=[(1,0),(1,1)]))


class RemapTests(unittest.TestCase):
    def test_native_vertex_glow_keeps_environment_and_other_layouts_separate(self):
        a=entry();a['table_version']=177;a['texture_ids'][:2]=[-1,-1]
        a['fields']['vertAlbedo']=1
        self.assertTrue(native_vertex_glow(a,169))
        a['table_version']=202
        self.assertTrue(native_vertex_glow(a,175))
        self.assertFalse(native_vertex_glow(a,169))
        a['fields']['shadedGlow']=1
        self.assertFalse(native_vertex_glow(a,175))
        a['fields']['shadedGlow']=0;a['texture_ids'][0]=0
        self.assertFalse(native_vertex_glow(a,175))
        a['texture_ids'][0]=-1;a['fields']['vertAlbedo']=0
        self.assertFalse(native_vertex_glow(a,175))

    def test_common_binding_does_not_select_a_shader_variant(self):
        a=entry();b=copy.deepcopy(a)
        a['fields'].update(skinned=0,numBones=0)
        b['fields'].update(skinned=1,numBones=4)
        result=shared_glow_binding([a,b],'DeclaredGlow',169)
        self.assertEqual((result['texture'],result['uv'],result['candidates']),(6,1,2))
        self.assertNotIn('material_index',result)

    def test_conflicting_binding_refuses_in_both_orders(self):
        a=entry();b=entry();b['texture_ids'][1]=7
        for candidates in ([a,b],[b,a]):
            with self.assertRaisesRegex(FormatError,'disagree'):
                shared_glow_binding(candidates,'DeclaredGlow',169)

    def test_non_additive_and_unknown_layouts_remain_unassigned(self):
        for key,value in [('glow',0),('shadedGlow',1),('layerBlendDiffuse0',4),('layerBlendDiffuse1',2)]:
            a=entry();a['fields'][key]=value
            self.assertIsNone(shared_glow_binding([a],'DeclaredGlow',169))
        a=entry();a['table_version']=177
        self.assertIsNone(shared_glow_binding([a],'DeclaredGlow',169))
        self.assertIsNone(shared_glow_binding([entry()],'DeclaredGlow',175))

    def test_bad_uv_and_missing_declared_name_refuse(self):
        for uv in [(0,1),(1,16),(1,0xffffffff)]:
            a=entry();a['fields']['uvSets'][1]=uv
            with self.assertRaises(FormatError):shared_glow_binding([a],'DeclaredGlow',169)
        with self.assertRaises(FormatError):shared_glow_binding([entry()],'declaredglow',169)


if __name__=='__main__':unittest.main()
