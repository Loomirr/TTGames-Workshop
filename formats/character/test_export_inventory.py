"""Assembly-loss checks independent of Blender or proprietary fixtures."""
import copy
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest


root = Path(__file__).resolve().parents[2]
package = ModuleType('inventory_fixture')
package.__path__ = [str(Path(__file__).parent / 'Addon/io_scene_tt_character')]
sys.modules[package.__name__] = package
core = ModuleType(package.__name__ + '._core')
core.__path__ = [str(root / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[core.__name__] = core
from inventory_fixture.export_inventory import bind_inventory, check_inventory
from inventory_fixture._core.cu3 import FormatError


class Object(dict):
    def __init__(self, name, kind='ARMATURE', **properties):
        super().__init__(properties)
        self.name, self.type, self.children, self.mode = name, kind, [], 'OBJECT'

    @property
    def children_recursive(self):
        return [item for child in self.children for item in [child] + child.children_recursive]


def specimen():
    rig = Object('Body', tt_native_source='source/Body.GHG')
    mesh = Object('Body draw', 'MESH', source_part=1, source_special=2,
                  tt_native_rigid_joint=-1, tt_vertex_transform='identity')
    attachment = Object('Helmet', tt_native_source='source/Helmet.GHG')
    helmet = Object('Helmet draw', 'MESH', source_part=3, source_special=4,
                    tt_native_rigid_joint=0, tt_vertex_transform='identity')
    attachment.children.append(helmet)
    rig.children.extend((mesh, attachment))
    bind_inventory(rig)
    return rig, mesh, attachment, helmet


class InventoryTests(unittest.TestCase):
    def test_unchanged_and_renamed_objects(self):
        rig, mesh, attachment, helmet = specimen()
        for obj in (rig, mesh, attachment, helmet):
            obj.name += ' user label'
        result = check_inventory(rig)
        self.assertTrue(result['checked'])
        self.assertEqual((result['mesh_draws'], result['model_instances']), (2, 2))

    def test_removed_mesh(self):
        rig, mesh, *_ = specimen()
        rig.children.remove(mesh)
        with self.assertRaisesRegex(FormatError, 'meshes were added, removed'):
            check_inventory(rig)

    def test_removed_whole_attachment(self):
        rig, mesh, attachment, _ = specimen()
        rig.children.remove(attachment)
        with self.assertRaisesRegex(FormatError, 'attachment was removed or detached'):
            check_inventory(rig)

    def test_new_unbound_geometry(self):
        rig, *_ = specimen()
        rig.children.append(Object('New cube', 'MESH'))
        with self.assertRaisesRegex(FormatError, 'New or unbound mesh'):
            check_inventory(rig)

    def test_new_geometry_hidden_under_empty(self):
        rig, *_ = specimen()
        empty = Object('helper', 'EMPTY')
        empty.children.append(Object('New cube', 'MESH'))
        rig.children.append(empty)
        with self.assertRaisesRegex(FormatError, 'outside its imported native model'):
            check_inventory(rig)

    def test_duplicate_draw(self):
        rig, mesh, *_ = specimen()
        rig.children.append(copy.deepcopy(mesh))
        with self.assertRaisesRegex(FormatError, 'duplicated'):
            check_inventory(rig)

    def test_whole_model_copy_is_allowed_for_proposal_comparison(self):
        rig, mesh, attachment, helmet = specimen()
        rig.children.append(copy.deepcopy(attachment))
        result = check_inventory(rig)
        self.assertEqual((result['mesh_draws'], result['model_instances']), (3, 3))

    def test_reparented_draw_rejected(self):
        rig, mesh, attachment, _ = specimen()
        rig.children.remove(mesh)
        attachment.children.append(mesh)
        with self.assertRaises(FormatError):
            check_inventory(rig)

    def test_changed_native_binding_rejected(self):
        rig, mesh, *_ = specimen()
        mesh['source_part'] += 1
        with self.assertRaisesRegex(FormatError, 'rebound'):
            check_inventory(rig)

    def test_new_source_model_rejected(self):
        rig, mesh, attachment, helmet = specimen()
        extra = copy.deepcopy(attachment)
        extra['tt_native_source'] = 'source/NewHelmet.GHG'
        rig.children.append(extra)
        with self.assertRaisesRegex(FormatError, 'Adding a native model'):
            check_inventory(rig)

    def test_old_import_is_explicitly_unchecked(self):
        rig, *_ = specimen()
        del rig['tt_native_export_inventory']
        result = check_inventory(rig)
        self.assertFalse(result['checked'])
        self.assertIn('Deleted meshes', result['warnings'][0])

    def test_edit_mode_rejected_including_old_import(self):
        rig, mesh, *_ = specimen()
        mesh.mode = 'EDIT'
        for old in (False, True):
            if old:
                del rig['tt_native_export_inventory']
            with self.assertRaisesRegex(FormatError, 'Leave Edit Mode'):
                check_inventory(rig)

    def test_invalid_inventory_is_not_treated_as_legacy(self):
        rig, *_ = specimen()
        for invalid in ('not json', '{}', json.dumps({'schema': 'future.v2'})):
            rig['tt_native_export_inventory'] = invalid
            with self.assertRaises(FormatError):
                check_inventory(rig)


if __name__ == '__main__':
    unittest.main()
