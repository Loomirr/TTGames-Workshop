"""Manual GUI/dispatch checks using generated inputs, without game assets."""
from pathlib import Path
import queue
import struct
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest

import workshop_gui as gui


class ToolboxChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source & special.btga'
        raw = bytearray(56)
        raw[:12] = bytes.fromhex('0004000010000000f2ffffff')
        struct.pack_into('<IHHIII', raw, 20, 256, 8, 8, 256, 0, 1)
        self.source.write_bytes(raw + bytes([255, 20, 40, 60]) * 64)

    def command(self, output):
        return gui.build_command('3DS BTGA to DDS / PNG', [str(self.source), str(output)])

    def test_literal_paths_and_existing_output_protection(self):
        out = self.root / 'out & space'
        cmd, paths = self.command(out)
        self.assertEqual(cmd[-2:], [str(self.source), str(out)])
        self.assertEqual(paths, [out])
        out.mkdir()
        with self.assertRaisesRegex(ValueError, 'NEW'):
            self.command(out)

    def test_source_tree_and_cache_protection(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            gui.build_command('LMSH1 decoded animation to BVH', [str(self.root), str(self.root / 'nested'), '30'])
        with self.assertRaisesRegex(ValueError, 'outside'):
            gui.build_command('CU3 dependency report', [str(self.source), str(self.root), 'LB3', str(self.root / 'cache'), str(self.root.parent / 'new-report.json')])

    def test_invalid_fps(self):
        for fps in ('0', 'nan', '-2', '1000'):
            with self.assertRaises(ValueError):
                gui.build_command('LMSH1 decoded animation to BVH', [str(self.root), str(self.root / 'out'), fps])

    def test_all_forms_dispatch_to_present_scripts(self):
        for name, (script, _, fields) in gui.TOOLS.items():
            self.assertTrue((gui.ROOT / script).is_file(), name)
            values = []
            for _, kind, _, default in fields:
                values.append(str(self.source) if kind in ('file', 'source') else
                              str(self.root / 'inputs') if kind == 'dir' else
                              str(self.root / ('cache' if kind == 'cache' else 'result')) if kind in ('cache', 'outfile', 'outdir') else
                              default or 'ExactActor')
            (self.root / 'inputs').mkdir(exist_ok=True)
            command, _ = gui.build_command(name, values)
            self.assertEqual(command[2], str(gui.ROOT / script))

    def test_worker_success_and_failure(self):
        output = self.root / 'converted'
        original = self.source.read_bytes()
        events = queue.Queue()
        gui.run_command(self.command(output)[0], events)
        records = list(events.queue)
        self.assertEqual(records[-1], ('done', 0), records)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertTrue((output / (self.source.stem + '.dds')).is_file())
        self.source.write_bytes(b'invalid header')
        events = queue.Queue()
        gui.run_command(self.command(self.root / 'failed')[0], events)
        self.assertNotEqual(list(events.queue)[-1], ('done', 0))
        self.assertFalse((self.root / 'failed').exists())

    def test_tk_forms_and_responsive_worker(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = gui.Workshop(root)
            for name, (_, _, fields) in gui.TOOLS.items():
                app.choice.set(name)
                app.select()
                root.update()
                self.assertEqual(len(app.values), len(fields))
            app.choice.set('3DS BTGA to DDS / PNG')
            app.select()
            app.values[0].set(str(self.source))
            app.values[1].set(str(self.root / 'gui-output'))
            app.run()
            self.assertTrue(app.running)
            deadline = time.monotonic() + 20
            ticks = 0
            while app.running and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
                ticks += 1
            self.assertFalse(app.running, 'GUI job did not complete')
            self.assertGreater(ticks, 1)
            self.assertIn('Finished', app.status.cget('text'))
            self.assertTrue((self.root / 'gui-output' / 'Manifest.json').exists())
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
