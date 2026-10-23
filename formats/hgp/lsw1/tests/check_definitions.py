"""Character layer selection: comments, scope, exact sets and bad references."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from check_layer_assembly import layers, part

spec = importlib.util.spec_from_file_location('lsw1_definition', Path(__file__).parents[1] / 'definition.py')
definition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(definition)


class DefinitionTests(unittest.TestCase):
    def test_comments_and_nested_animation_overrides_are_not_top_level(self):
        text = '''/* layers_high=9 */
layers_high=1, 3 // selected
anim_start="idle; // not a comment"
layers_high=0
effect_start
layers_high=7
effect_end
anim_end
; layers_high=8
layers_low=2
'''
        self.assertEqual(definition.parse_layer_sets(text), {'high': [1, 3], 'low': [2]})

    def test_exact_set_does_not_add_default_or_other_detail(self):
        h = layers(['default', 'replacement', 'extra'],
                   [[part(1, [1])], [part(2, [1])], [part(3, [2])]])
        selected = definition.parse_layer_sets('layers_high=1,2,1')['high']
        self.assertEqual([p['geometry'] for p in h.meshes_for_layers(selected)], [2, 3])

    def test_invalid_unselected_set_does_not_block_valid_selection(self):
        # Original Anakin pod definitions contain a period in layers_low.
        self.assertEqual(definition.parse_layer_sets('layers_high=0,1\nlayers_low=1,4.6,7', only='high'),
                         {'high': [0, 1]})
        with self.assertRaisesRegex(ValueError, 'Invalid layers_low'):
            definition.parse_layer_sets('layers_low=1,4.6,7', only='low')

    def test_bad_lists_duplicates_and_unclosed_blocks_are_refused(self):
        for text in ('layers_high=-1', 'layers_high=0,', 'layers_high=32',
                     'layers_high=0\nlayers_high=1', 'layers_high=0;ok\nanim_start="idle"',
                     'anim_end', '/* unfinished', 'name="unfinished'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                definition.parse_layer_sets(text)

    def test_same_stem_companion_and_layer_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hgp = root / 'Character.hgp'
            hgp.write_bytes(b'')
            txt = root / 'CHARACTER.txt'
            txt.write_text('layers_high=1\nlayers_low=3', encoding='utf-8')
            self.assertEqual(definition.companion(hgp, '.txt'), txt)
            self.assertEqual(definition.read_layer_set(txt, 'high', 2), [1])
            with self.assertRaisesRegex(ValueError, 'unavailable layers'):
                definition.read_layer_set(txt, 'low', 2)
            with self.assertRaisesRegex(ValueError, 'no layers_dead'):
                definition.read_layer_set(txt, 'dead', 2)
            with self.assertRaisesRegex(ValueError, 'found 0'):
                definition.companion(root / 'Other.hgp', '.txt')


if __name__ == '__main__':
    unittest.main()
