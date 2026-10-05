"""Asset-free checks for CD selection of alternatives within a native layer."""
import sys
import types
import unittest
from pathlib import Path

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.native_layers import selected_layer_metadata


class LayerSelection(unittest.TestCase):
    def setUp(self):
        self.skeleton = {'layers': [
            {'name':'TT0_Arm', 'metadata_index':0, 'rigids':0, 'skins':3},
            {'name':'TT1_Cape', 'metadata_index':3, 'rigids':0, 'skins':2}],
            'layer_metadata':[{'layer':0,'special':i} for i in range(3)] +
                             [{'layer':1,'special':i} for i in range(3,5)]}
        self.display = {'specials':[{'name':name} for name in ('Arm','Robot','Skeleton','BatCape','Cape')]}
        self.definition = {'character':{'Use Default Layers':0,'Cutscene Layers':3},'objects':[]}

    def select(self):
        return [m['special'] for m in selected_layer_metadata(self.skeleton,self.display,self.definition)]

    def override(self, index, name, field='Layer'):
        self.definition['objects'].append({'class':'Character Layer Special','fields':{field:index,'Layer Special':name}})

    def test_default_selects_one_alternative(self):
        self.assertEqual(self.select(),[0,3])

    def test_explicit_default_costume_with_empty_cutscene_mask(self):
        self.definition['character'].update({'Default Layers':1,'Cutscene Layers':0,'Use Default Layers':-64})
        self.assertEqual([m['special'] for m in selected_layer_metadata(self.skeleton,self.display,self.definition,layer_mode='default')],[0])
        self.assertEqual(selected_layer_metadata(self.skeleton,self.display,self.definition,layer_mode='cutscene'),[])

    def test_named_cape_selects_exact_source_special(self):
        self.override(1,'Cape')
        self.assertEqual(self.select(),[0,4])

    def test_all_preserves_multiple_parts(self):
        self.override(0,'All')
        self.assertEqual(self.select(),[0,1,2,3])

    def test_nxg_layer_id(self):
        self.override(0,'Robot','Layer Id')
        self.assertEqual(self.select(),[1,3])

    def test_disabled_layer_does_not_draw(self):
        self.definition['character']['Cutscene Layers']=1
        self.assertEqual(self.select(),[0])

    def test_unconfigured_inspection_keeps_alternatives(self):
        self.assertEqual(len(selected_layer_metadata(self.skeleton,self.display)),5)

    def test_missing_named_special_rejected(self):
        self.override(1,'Unknown')
        with self.assertRaises(FormatError):self.select()

    def test_conflicting_selection_rejected(self):
        self.override(0,'All');self.override(0,'Robot')
        with self.assertRaises(FormatError):self.select()

    def test_bad_metadata_layer_rejected(self):
        self.skeleton['layer_metadata'][0]['layer']=1
        with self.assertRaises(FormatError):self.select()

    def test_layer_mask_above_32_bits(self):
        self.skeleton['layers'] = [{'name':'','metadata_index':0,'rigids':0,'skins':0} for _ in range(34)]
        self.skeleton['layers'][33]={'name':'TT33_Breakup','metadata_index':0,'rigids':0,'skins':1}
        self.skeleton['layer_metadata']=[{'layer':33,'special':0}]
        self.definition['character']['Cutscene Layers']=1<<33
        self.assertEqual(self.select(),[0])


if __name__=='__main__':unittest.main()
