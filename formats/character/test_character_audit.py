"""Portable roster audit tests. No Blender or proprietary files."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import audit_characters as audit


class AuditTests(unittest.TestCase):
    def test_index_refusal_is_a_report_not_a_whole_run_traceback(self):
        error=ValueError('Unknown archive extension')
        error.diagnostics={'status':'unsupported_suffix'}
        with patch.object(audit,'open_assets',side_effect=error):
            result=audit.audit(Path('game'),'TFA',Path('cache'))
        self.assertEqual(result['status'],'asset_index_failed')
        self.assertEqual(result['checked'],0)
        self.assertEqual(result['diagnostic'],error.diagnostics)

    def test_filter_and_cutscene_layers_use_importer_validation(self):
        root=Path('assets')
        paths=[root/'chars/minifig/Hero/Hero.cd',root/'chars/minifig/Other/Other.cd']
        assets=SimpleNamespace(root=root,files={p.name.lower():[p] for p in paths},find_exact=lambda p:root/p)
        definition={'version':28,'character':{},'objects':[]}
        model={'skeleton':{'joints':[]},'mesh_version':175,'validation':{'material_versions':[202]}}
        resolver=SimpleNamespace(resolve_definition_model=lambda d,p:p.with_suffix('.ghg'))
        with (patch.object(audit,'open_assets',return_value=assets),
              patch.object(audit,'character_definition',return_value=definition),
              patch.object(audit,'ResourceResolver',return_value=resolver),
              patch.object(audit,'load_model',return_value=model),
              patch.object(audit,'selected_draws',return_value=[({}, {'part':0,'material':0}, None)]) as draws,
              patch.object(audit,'validate_draw') as validate,
              patch.object(audit,'active_attachments',return_value=[]) as attachments):
            result=audit.audit(root,'LB3',Path('cache'),contains='/HERO/',layer_mode='cutscene')
        self.assertEqual(result['discovered'],2)
        self.assertEqual(result['checked'],1)
        self.assertEqual(result['parser_ready'],1)
        self.assertEqual(draws.call_args.kwargs,dict(layer_mode='cutscene',highest_detail=True))
        self.assertEqual(attachments.call_args.kwargs['layer_mode'],'cutscene')
        validate.assert_called_once()

    def test_invalid_requests_refused(self):
        for options in ({'limit':-1},{'layer_mode':'guessed'}):
            with self.assertRaises(ValueError):audit.audit(Path('.'),'LB3',Path('cache'),**options)


if __name__=='__main__':unittest.main()
