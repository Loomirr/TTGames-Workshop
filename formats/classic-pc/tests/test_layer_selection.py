"""Asset-free TCS visibility rules; unknown input keeps every native layer."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from layer_selection import configured_layers, parse_high_layers


class HighLayers(unittest.TestCase):
    def test_only_explicit_high_with_comments(self):
        text = '\ufeff// layers_high=99\n layers_low=4\nLAYERS_HIGH = 0, 2, 5 ; note\nlayers_dead=6'
        self.assertEqual(parse_high_layers(text, 7), [0, 2, 5])

    def test_unsupported_or_ambiguous_remains_unknown(self):
        for text in ('layers_special=0,1', 'txt_file="another"',
                     'layers_high=', 'layers_high=-1', 'layers_high=0,7',
                     'layers_high=0,0', 'layers_high=0 1', 'layers_high="0,1"',
                     'layers_high=0,', 'layers_high=0\nlayers_high=1',
                     'layers_high=999999999999999999999999',
                     'layers_high 0,1'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_high_layers(text, 7)

    def test_no_accidental_multiline_list(self):
        # A one-line directive does not absorb unrelated subsequent numbers.
        self.assertEqual(parse_high_layers('layers_high=0\n2,3', 7), [0])

    def test_layer_count_guard(self):
        for count in (0, -1, 4097, None):
            with self.assertRaises(ValueError):
                parse_high_layers('layers_high=0', count)

    def test_matching_sibling_case_and_pc_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'Hero.TxT').write_text('layers_high=0,2\nlayers_low=1', encoding='ascii')
            result = configured_layers(root/'HERO_PC.GHG', 3)
            self.assertEqual(result['status'], 'configured_high')
            self.assertEqual(result['selected'], [0, 2])
            # Do not assign high-model indices to a separate low-model table.
            self.assertEqual(configured_layers(root/'HERO_LR_PC.GHG', 3)['status'], 'all_layers_fallback')

    def test_missing_and_invalid_definition_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder)/'Hero_PC.GHG'
            self.assertIsNone(configured_layers(model, 3)['selected'])
            (model.parent/'Hero.txt').write_text('layers_high=0,5', encoding='ascii')
            result = configured_layers(model, 3)
            self.assertIsNone(result['selected'])
            self.assertIn('outside', result['reason'])

    def test_size_limit_and_binary_text(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder)/'Hero_PC.GHG'
            txt = model.parent/'Hero.txt'
            txt.write_bytes(b'layers_high=0\0')
            self.assertIn('NUL', configured_layers(model, 3)['reason'])
            txt.write_bytes(b'layers_high=0')
            with patch('layer_selection.MAX_DEFINITION_BYTES', 4):
                self.assertIn('limit', configured_layers(model, 3)['reason'])

    def test_ambiguous_case_names_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            a = Path(folder)/'Hero.txt'
            a.write_text('layers_high=0', encoding='ascii')
            # Works on both case-sensitive and case-insensitive filesystems.
            with patch.object(Path, 'iterdir', return_value=iter([a, a])):
                self.assertIn('Ambiguous', configured_layers(a.with_suffix('.ghg'), 2)['reason'])


if __name__ == '__main__':
    unittest.main()
