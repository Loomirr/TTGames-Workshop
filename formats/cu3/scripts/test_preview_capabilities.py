"""Capability/report behavior; no claim of Blender geometry execution."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

package=types.ModuleType('capability_fixture')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
blender=types.ModuleType('bpy');blender.types=types.SimpleNamespace()
blender.app=types.SimpleNamespace(version=(4,4,0))
with patch.dict(sys.modules,{'bpy':blender}):
    from capability_fixture.geometry_normals import normal_preservation_status,capture_normals


class CapabilityTests(unittest.TestCase):
    def test_older_blender_reports_fidelity_limit_without_constructing_nodes(self):
        report=normal_preservation_status()
        self.assertFalse(report['supported'])
        self.assertIn('cannot preserve',report['limitation'])
        geometry=object()
        # No node/links objects: a supported fallback must not try to use them.
        self.assertEqual(capture_normals(None,None,geometry),(geometry,None))

    def test_feature_detection_not_version_guessing(self):
        with patch.object(blender,'types',types.SimpleNamespace(GeometryNodeSetMeshNormal=object())):
            report=normal_preservation_status()
        self.assertTrue(report['supported'])
        self.assertIsNone(report['limitation'])
        self.assertEqual(report['blender_version'],[4,4,0])


if __name__=='__main__':unittest.main()
