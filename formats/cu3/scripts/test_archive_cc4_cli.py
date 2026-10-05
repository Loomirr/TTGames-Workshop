"""CLI help and overwrite protection checks; no game archives required."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('archive_index_cc4.py')


class ArchiveCliChecks(unittest.TestCase):
    def test_help_does_not_open_an_archive(self):
        result=subprocess.run([sys.executable,str(SCRIPT),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('New index JSON filename',result.stdout)

    def test_existing_output_is_preserved_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'previous.json';target.write_bytes(b'keep this report')
            result=subprocess.run([sys.executable,str(SCRIPT),str(root/'missing.dat'),str(target)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('new output filename',result.stderr)
            self.assertEqual(target.read_bytes(),b'keep this report')


if __name__=='__main__':unittest.main()
