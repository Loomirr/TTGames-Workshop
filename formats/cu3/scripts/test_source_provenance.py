"""Synthetic consumed-revision and rollback checks; no game format claims."""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace,ModuleType
addon=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=ModuleType('io_scene_lego_cu3');package.__path__=[str(addon)]
sys.modules.setdefault('io_scene_lego_cu3',package)
from io_scene_lego_cu3.source_provenance import SourceProvenance
from io_scene_lego_cu3.cu3 import FormatError

class ProvenanceTests(unittest.TestCase):
    def test_shared_revision_rollback_keeps_prior_and_later_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);paths=[root/n for n in ('body.TEX','earlier.CD','failed.TEX','later.TEX')]
            for i,p in enumerate(paths):p.write_bytes(bytes([i]))
            ledger=SourceProvenance(SimpleNamespace(root=root,files={},profile='synthetic'))
            for p in paths[:2]:ledger.record(p,'surviving')
            before=ledger.snapshot()
            ledger.record(paths[0],'failed-shared');ledger.record(paths[2],'failed')
            ledger.restore(before);ledger.record(paths[3],'later')
            self.assertEqual(set(ledger.verify()),{paths[0],paths[1],paths[3]})
            self.assertEqual(ledger.records[str(paths[0])]['roles'],['surviving'])
            self.assertEqual(SourceProvenance.loads(ledger.dumps()).verify(),ledger.verify())

    def test_changed_or_missing_companions_fail(self):
        for role in ('character-definition','texture','animation-set','animation','animation-bank'):
            with self.subTest(role=role),tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/'source';p.write_bytes(b'consumed')
                ledger=SourceProvenance();ledger.record(p,role,data=b'consumed')
                p.write_bytes(b'changed')
                with self.assertRaisesRegex(FormatError,'changed since import'):ledger.verify()
                p.unlink()
                with self.assertRaisesRegex(FormatError,'missing/unreadable'):ledger.verify()

    def test_same_path_cannot_acquire_a_new_consumed_revision(self):
        ledger=SourceProvenance();ledger.record('sample','model',data=b'old')
        with self.assertRaisesRegex(FormatError,'changed while being consumed'):
            ledger.record('sample','texture',data=b'new')

    def test_archive_member_identity_and_bank_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'GAME.DAT';archive.write_bytes(b'container')
            path=root/'CACHE/BANK.PAK';path.parent.mkdir();path.write_bytes(b'bank')
            entry=dict(path='BANK.PAK',offset=8,packed_size=4,size=4)
            assets=SimpleNamespace(root=path.parent,profile='sample',files={'bank.pak':[(archive,entry)]})
            ledger=SourceProvenance(assets);ledger.record(path,'bank-index',data=b'bank',export=False)
            self.assertEqual(ledger.verify(),{})
            ledger.record(path,'bank',data=b'bank',member=dict(name='idle.AN4',offset=1,size=2))
            record=ledger.records[str(path)]
            self.assertEqual(record['archive_members'][0]['offset'],8)
            self.assertEqual(record['animation_members'][0]['name'],'idle.AN4')
            self.assertEqual(ledger.verify(),{path:b'bank'})

    def test_old_imports_require_reimport(self):
        with self.assertRaisesRegex(FormatError,'reimport'):SourceProvenance.loads(None)

if __name__=='__main__':unittest.main()
