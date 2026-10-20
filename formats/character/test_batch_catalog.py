"""Portable batch discovery checks: loose/archive parity and explicit scope."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('batch_catalog', Path(__file__).parent/'Addon/io_scene_tt_character/batch_catalog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BatchCatalogTests(unittest.TestCase):
    def assets(self, archive=False):
        paths = ['chars/minifigs/Hero/Hero.cd', 'chars/minifigs/super_characters/Base.cd',
                 'chars/vehicles/Car/Car_NXG.ghg', 'chars/vehicles/Car/Car.cd',
                 'levels/Stage/Stage.gsc', 'chars/Props/Box.ghg']
        files = {}
        for p in paths:
            files.setdefault(Path(p).name.lower(), []).append((None, {'path':p}) if archive else Path('/assets')/p)
        return SimpleNamespace(root=Path('/assets'), profile='LMSH1', files=files)

    def test_archive_loose_parity(self):
        for scope in ('CHARACTERS','VEHICLES','DEFINITIONS','MODELS','ALL'):
            self.assertEqual(module.catalog_paths(self.assets(), scope), module.catalog_paths(self.assets(True), scope))
        self.assertEqual(len(module.catalog_paths(self.assets(), 'CHARACTERS')), 1)
        self.assertEqual(module.catalog_paths(self.assets(), 'VEHICLES'), ['chars/vehicles/Car/Car_NXG.ghg'])
        self.assertEqual(len(module.catalog_paths(self.assets(), 'ALL')), 6)

    def test_filter_and_resume(self):
        paths = module.catalog_paths(self.assets(), 'ALL', 'CAR')
        self.assertEqual(len(paths), 2)
        self.assertEqual(module.select_paths(paths, 1, 0), paths[1:])
        self.assertEqual(module.select_paths(paths, 3, 20), [])
        with self.assertRaises(ValueError):module.select_paths(paths, -1, 2)
        with self.assertRaises(ValueError):module.catalog_paths(self.assets(), 'INVALID')

    def test_classic_preserves_underscore_and_excludes_low_detail(self):
        assets = SimpleNamespace(root=Path('/assets'), profile='TCS', files={
            '_yoda.ghg': [Path('/assets/chars/_Yoda.ghg')],
            '_yoda_lr_pc.ghg':[Path('/assets/chars/_Yoda_LR_PC.ghg')]})
        self.assertEqual(module.catalog_paths(assets), ['chars/_Yoda.ghg'])


if __name__ == '__main__':unittest.main()
