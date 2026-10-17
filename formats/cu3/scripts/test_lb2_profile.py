"""Experimental LEGO Batman 2 character profile: MESH 48 only, single costume UV pair."""
import sys
import types
import unittest
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('lb2_profile_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from lb2_profile_fixture.profiles import character_profile, validate_profile_model
from lb2_profile_fixture.native_materials import costume_uv_index
from lb2_profile_fixture.cu3 import FormatError


class LB2Profile(unittest.TestCase):
    def test_profile_accepts_only_mesh_48(self):
        profile=character_profile('LB2')
        self.assertEqual((profile['renderer'],profile['model_suffix']),('NXG','_NXG'))
        validate_profile_model('LB2','chars/minifigs/batman/batman_nxg.ghg',48)
        validate_profile_model('LB2','chars/props/prop_nxg.gsc',48)
        for version in (47,169,175):
            with self.assertRaises(FormatError):validate_profile_model('LB2','x_nxg.ghg',version)
        with self.assertRaises(FormatError):validate_profile_model('LB2','x_dx11.ghg',48)

    def test_costume_prints_use_the_only_uv_pair(self):
        for name in ('BODY_FRONT_GAME','LEFTARM_GAME','HEAD_FRONT_GAME','Prop'):
            entry=dict(name=name,table_version=132,fields=dict(uvSets=[]),render_flags=dict(special_id=0))
            self.assertEqual(costume_uv_index(entry,48),0)


if __name__=='__main__':
    unittest.main()
