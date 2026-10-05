"""Portable stage command bounds, material ownership and separator checks."""
import copy,sys,types,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('stage_fixture');package.__path__=[str(root)];sys.modules[package.__name__]=package
from stage_fixture.stage_geometry import decode_stage_commands
from stage_fixture.cu3 import FormatError


def fixture():
    return {'commands':[(0x84,4,0),(0x85,1,6),(0x80,3,0),(0x8b,1,0),
                        (0x83,0,0),(0xb3,0,0),(0x84,4,0),(0x87,0,0),
                        (0x83,0,1),(0xb3,0,1),(0x8e,0,0)],
            'specials':[{'index':0,'clip':0}], 'clips':[{'materials':[2],'items':[9]}]}


class StageGeometry(unittest.TestCase):
    def test_static_and_named_materials_are_separate(self):
        result=decode_stage_commands(fixture(),2,2,3)
        self.assertEqual([x['part'] for x in result['static_candidates']],[0])
        self.assertEqual(result['static_candidates'][0]['material'],0)
        self.assertEqual(result['named_draws'][0]['material'],2)
        self.assertFalse(result['can_render_faithfully'])

    def test_out_of_range_matrix_part_material_and_jump(self):
        for command,value in ((1,99),(2,3),(4,2),(5,2)):
            data=fixture();op,flag,_=data['commands'][command];data['commands'][command]=(op,flag,value)
            with self.subTest(command=command),self.assertRaises(FormatError):decode_stage_commands(data,2,2,3)

    def test_unknown_commands_and_flags_rejected(self):
        for replacement in ((0x99,0,0),(0x83,7,0)):
            data=fixture();data['commands'][4]=replacement
            with self.assertRaises(FormatError):decode_stage_commands(data,2,2,3)

    def test_no_global_material_fallback_for_specials(self):
        data=fixture();data['specials']=[]
        with self.assertRaisesRegex(FormatError,'special material'):decode_stage_commands(data,2,2,3)
        data=fixture();data['clips'][0]['items']=[5]
        with self.assertRaisesRegex(FormatError,'command section'):decode_stage_commands(data,2,2,3)

    def test_ambiguous_special_materials_rejected(self):
        data=fixture();data['specials'].append({'index':1,'clip':1});data['clips'].append({'materials':[1],'items':[9]})
        with self.assertRaisesRegex(FormatError,'unambiguous'):decode_stage_commands(data,2,2,3)

    def test_boundary_and_unbound_draw_rejected(self):
        data=fixture();data['commands'][7]=(0x84,4,0)
        with self.assertRaisesRegex(FormatError,'boundaries'):decode_stage_commands(data,2,2,3)
        data=fixture();data['commands'][8]=(0xb0,3,1)
        with self.assertRaisesRegex(FormatError,'matrix binding'):decode_stage_commands(data,2,2,3)


if __name__=='__main__':unittest.main()
