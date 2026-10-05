"""New CU3 envelope support must not silently enable an older camera footer."""
import sys
import types
import unittest
from pathlib import Path

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.cinematic import read_cameras


class CameraVersionGate(unittest.TestCase):
    def test_unverified_footers_rejected_before_reading(self):
        for version in (20,21,22,23,24,25,26,27,30,31):
            with self.subTest(version=version), self.assertRaisesRegex(FormatError,'footer is not yet verified'):
                read_cameras(types.SimpleNamespace(version=version))


if __name__=='__main__':unittest.main()
