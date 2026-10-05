"""Version selection and copy preservation, using temporary toy packages."""
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import uuid
from contextlib import contextmanager
import unittest
from prune_builds import keep_latest


@contextmanager
def temporary_tree():
    base=Path(tempfile.gettempdir()).resolve()
    root=base / ('tt-build-retention-' + uuid.uuid4().hex)
    root.mkdir()
    try:
        yield root
    finally:
        if not root.resolve().is_relative_to(base):
            raise ValueError('Test directory escaped temporary root')
        shutil.rmtree(root)


class BuildRetention(unittest.TestCase):
    def setup_tree(self, root):
        builds = root / 'builds'
        builds.mkdir()
        packages = []
        for name in ['blender/Tool_0.2.0.zip','blender/Tool_0.10.0.zip','windows/Other-0.1.0-win64.zip']:
            p = builds / name
            p.parent.mkdir(exist_ok=True)
            data = name.encode()
            p.write_bytes(data)
            packages.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        (builds/'manifest.json').write_text(json.dumps(dict(packages=packages)))
        return builds

    def test_numeric_versions_and_preserved_old_package(self):
        with temporary_tree() as temp:
            root = Path(temp);builds = self.setup_tree(root);archive = root/'history'
            self.assertEqual(keep_latest(builds,archive),['blender/Tool_0.2.0.zip'])
            self.assertTrue((builds/'blender/Tool_0.2.0.zip').exists())
            keep_latest(builds,archive,apply=True)
            self.assertEqual((archive/'blender/Tool_0.2.0.zip').read_bytes(),b'blender/Tool_0.2.0.zip')
            self.assertFalse((builds/'blender/Tool_0.2.0.zip').exists())
            self.assertEqual(len(json.loads((builds/'manifest.json').read_text())['packages']),2)
            self.assertEqual(keep_latest(builds,archive),[])

    def test_changed_or_unlisted_packages_do_not_get_removed(self):
        for kind in ('changed','unlisted','conflicting_history'):
            with self.subTest(kind=kind), temporary_tree() as temp:
                root=Path(temp);builds=self.setup_tree(root);archive=root/'history'
                if kind=='changed':(builds/'blender/Tool_0.10.0.zip').write_bytes(b'changed')
                elif kind=='unlisted':(builds/'Unknown_1.0.0.zip').write_bytes(b'unknown')
                else:
                    (archive/'blender').mkdir(parents=True)
                    (archive/'blender/Tool_0.2.0.zip').write_bytes(b'other')
                with self.assertRaises(ValueError):keep_latest(builds,archive,apply=True)
                self.assertTrue((builds/'blender/Tool_0.2.0.zip').exists())


if __name__ == '__main__':unittest.main()
