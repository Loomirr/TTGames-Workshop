"""Synthetic cutscene/level registry tests without game assets or Blender."""
from pathlib import Path
import sys
import types
import unittest

package = types.ModuleType('tt_config_check')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_config_check.cu3 import FormatError
from tt_config_check.scene_configuration import commands, resolve_configuration, configuration_report, compile_character_replacements


def fixture():
    return {
        'cut/cutscenes_main.txt': 'txt_file "Cut/Story/Example.txt"\n',
        'cut/story/example.txt': '''cutscene_start
dir "Story/AnUnrelatedFolder"
file "MY_SCENE"
level "RealStage"
FindCommonObject "Prop;Blue" // Preserve the semicolon inside quotes.
// FindCommonObject "Ignored"
dont_draw_special "HiddenShop"
replace_character "SourceActor" with "VisibleActor"
EDL 3 20
cutscene_end
''',
        'levels/levels.txt': '''level_start
dir "Story\\A\\RealStage"
file "RealStage"
common_dir "Story\\A\\TECH"
common_file "SharedTech"
commonart_dir "Story\\B"
commonart_file "SharedArt"
unlit
level_end
'''}


def resolve(files):
    cut = types.SimpleNamespace(name='my_scene', version=19)
    return resolve_configuration(cut, lambda path: files[path.casefold()], 'LB3')


class ConfigurationTests(unittest.TestCase):
    def test_declared_stage_graph_and_unapplied_commands(self):
        result = resolve(fixture())
        self.assertEqual([stage['resource_prefix'] for stage in result['stages']],
                         ['LEVELS/Story/A/RealStage/RealStage', 'LEVELS/Story/A/TECH/SharedTech', 'LEVELS/Story/B/SharedArt'])
        self.assertEqual([p['name'] for p in result['common_objects']], ['Prop;Blue'])
        self.assertEqual(result['character_replacements'][0]['replacement'], 'VisibleActor')
        self.assertEqual(result['hidden_specials'][0]['name'], 'HiddenShop')
        self.assertFalse(result['applied'])

    def test_duplicate_scene_is_ambiguous(self):
        files = fixture()
        files['cut/story/example.txt'] *= 2
        with self.assertRaisesRegex(FormatError, 'found 2'):
            resolve(files)

    def test_duplicate_level_is_ambiguous(self):
        files = fixture()
        files['levels/levels.txt'] *= 2
        with self.assertRaisesRegex(FormatError, 'found 2'):
            resolve(files)

    def test_include_cycle_rejected(self):
        files = fixture()
        files['cut/story/example.txt'] += 'txt_file "CUT/CUTSCENES_MAIN.TXT"\n'
        with self.assertRaisesRegex(FormatError, 'Cyclic'):
            resolve(files)

    def test_path_escape_rejected(self):
        files = fixture()
        files['cut/cutscenes_main.txt'] = 'txt_file "../outside.txt"'
        with self.assertRaisesRegex(FormatError, 'inside the game root'):
            resolve(files)

    def test_incomplete_common_pair_rejected(self):
        files = fixture()
        files['levels/levels.txt'] = files['levels/levels.txt'].replace('common_file "SharedTech"', '')
        with self.assertRaisesRegex(FormatError, 'Incomplete'):
            resolve(files)

    def test_unterminated_block_rejected(self):
        files = fixture()
        files['cut/story/example.txt'] = files['cut/story/example.txt'].replace('cutscene_end', '')
        with self.assertRaisesRegex(FormatError, 'Unterminated'):
            resolve(files)

    def test_bad_quote_rejected(self):
        with self.assertRaisesRegex(FormatError, 'quote'):
            commands('file "bad', 'sample.txt')

    def test_unknown_profile_rejected(self):
        with self.assertRaisesRegex(FormatError, 'profile/version'):
            resolve_configuration(types.SimpleNamespace(name='TEST', version=27), lambda _: '', 'TFA')

    def test_missing_exact_file_is_reported(self):
        result = configuration_report(types.SimpleNamespace(name='TEST', version=19),
                                      lambda path: {}[path], 'LB3')
        self.assertEqual(result['status'], 'unresolved')
        self.assertEqual(result['configuration_files'][0]['reference'], 'CUT/CUTSCENES_MAIN.TXT')
        self.assertEqual(result['configuration_files'][0]['status'], 'unresolved')

    def test_include_depth_is_bounded(self):
        files = fixture()
        files['cut/cutscenes_main.txt'] = 'txt_file "cut/0.txt"'
        files.update({f'cut/{i}.txt': f'txt_file "cut/{i+1}.txt"' for i in range(40)})
        with self.assertRaisesRegex(FormatError, 'depth'):
            resolve(files)

    def test_unrelated_missing_include_is_explicit(self):
        files = fixture()
        files['cut/cutscenes_main.txt'] += 'txt_file "cut/missing.txt"\n'
        def read(path):
            if path.casefold() not in files:
                raise FileNotFoundError(path)
            return files[path.casefold()]
        result = configuration_report(types.SimpleNamespace(name='MY_SCENE', version=19), read, 'LB3')
        self.assertEqual(result['status'], 'partial_declarations')
        self.assertEqual(result['unresolved_includes'][0]['reference'], 'cut/missing.txt')
        self.assertEqual(result['level'], 'RealStage')

    def test_stray_unrelated_end_is_reported(self):
        files = fixture()
        files['levels/levels.txt'] += 'level_end\n'
        result = resolve(files)
        self.assertEqual(result['level'], 'RealStage')
        self.assertEqual(len(result['syntax_notes']), 1)

    def test_simple_character_replacement_compiles_exact_resource_map(self):
        result = resolve(fixture())
        self.assertEqual(compile_character_replacements(result), {'sourceactor':'VisibleActor'})

    def test_duplicate_character_replacement_rejected(self):
        rows = [{'original':'Hero','replacement':'Other'}, {'original':'HERO','replacement':'Other'}]
        with self.assertRaisesRegex(FormatError, 'Duplicate'):
            compile_character_replacements({'character_replacements':rows})

    def test_chained_and_cyclic_replacements_rejected(self):
        for target in ('Third', 'Hero'):
            rows = [{'original':'Hero','replacement':'Other'}, {'original':'Other','replacement':target}]
            with self.subTest(target=target), self.assertRaisesRegex(FormatError, 'ordering'):
                compile_character_replacements({'character_replacements':rows})

    def test_non_resource_replacement_names_rejected(self):
        for value in ('../Other', 'Chars/Other', 'Other.CD', 'Other Actor', '', 123):
            with self.subTest(value=value), self.assertRaisesRegex(FormatError, 'bare resource'):
                compile_character_replacements({'character_replacements':[{'original':'Hero','replacement':value}]})

    def test_unresolved_configuration_does_not_supply_replacements(self):
        with self.assertRaisesRegex(FormatError, 'unresolved'):
            compile_character_replacements({'status':'unresolved'})


if __name__ == '__main__':
    unittest.main()
