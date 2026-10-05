"""Synthetic DAT/LZ2K tests: no game payloads or external decoders required."""
import hashlib
import struct
import shutil
import sys
import tempfile
import types
import unittest
import zlib
import uuid
from pathlib import Path

package = types.ModuleType('io_scene_lego_cu3')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__,package)
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.archive_compression import decode_lz2k_chunk,decode_entry
from io_scene_lego_cu3.archive_assets import ArchiveAssetIndex,index_v6,_path_hash
from io_scene_lego_cu3.asset_index import open_assets,AssetIndex


def blocks(*values):
    bits=''
    for count,symbol,distance in values:
        for value,width in ((count,16),(0,5),(0,5),(0,9),(symbol,9),(0,4),(distance,4)):
            bits+=f'{value:0{width}b}'
    bits+='0'*(-len(bits)%8)
    return int(bits,2).to_bytes(len(bits)//8,'big')


def archive(path,payload=b'abc',name='SAMPLE.CD'):
    offset=256
    strings=name.encode('ascii')+b'\0'
    index=(struct.pack('<iI',-6,1)+struct.pack('<4I',1,len(payload),len(payload),0)+
           struct.pack('<IhhiI',1,0,-1,0,0)+struct.pack('<I',len(strings))+strings+
           struct.pack('<I',_path_hash(name)))
    path.write_bytes(struct.pack('<II',offset+len(payload),len(index))+bytes(offset-8)+payload+index)


class Compression(unittest.TestCase):
    def test_hobbit_parent_index_requires_explicit_version(self):
        with tempfile.NamedTemporaryFile(suffix='.dat',delete=False) as f:path=Path(f.name)
        try:
            archive(path)
            data=bytearray(path.read_bytes());offset=struct.unpack_from('<I',data)[0]
            struct.pack_into('<i',data,offset,-5);path.write_bytes(data)
            with self.assertRaises(FormatError):index_v6(path)
            self.assertEqual(index_v6(path,version_expected=-5)[0]['path'],'SAMPLE.CD')
        finally:path.unlink()

    def test_literal_block(self):
        self.assertEqual(decode_lz2k_chunk(blocks((3,65,0)),3),b'AAA')

    def test_overlapping_copy_across_blocks(self):
        self.assertEqual(decode_lz2k_chunk(blocks((1,65,0),(1,256,0)),4),b'AAAA')

    def test_copy_before_history_rejected(self):
        with self.assertRaises(FormatError):decode_lz2k_chunk(blocks((1,256,0)),3)

    def test_truncated_bits_rejected(self):
        with self.assertRaises(FormatError):decode_lz2k_chunk(blocks((3,65,0))[:3],3)

    def test_bad_constant_rejected(self):
        with self.assertRaises(FormatError):decode_lz2k_chunk(blocks((1,511,0)),3)

    def test_output_overrun_rejected(self):
        with self.assertRaises(FormatError):decode_lz2k_chunk(blocks((1,65,0),(1,256,0)),3)

    def test_stored_chunk(self):
        self.assertEqual(decode_entry(struct.pack('<4sII',b'LZ2K',3,3)+b'ABC',3),b'ABC')

    def test_deflate_and_zlib(self):
        expected=b'ABCD'*100
        for tag,window in ((b'DFLT',-15),(b'ZLIB',15)):
            c=zlib.compressobj(wbits=window);payload=c.compress(expected)+c.flush()
            self.assertEqual(decode_entry(struct.pack('<4sII',tag,len(expected),len(payload))+payload,len(expected)),expected)

    def test_declared_output_limit(self):
        payload=zlib.compress(b'A'*10000)
        with self.assertRaises(FormatError):decode_entry(struct.pack('<4sII',b'ZLIB',1,len(payload))+payload,1)

    def test_chunk_extent_rejected(self):
        with self.assertRaises(FormatError):decode_entry(struct.pack('<4sII',b'LZ2K',3,100)+b'ABC',3)

    def test_unknown_compression_rejected(self):
        with self.assertRaises(FormatError):decode_entry(b'ZIPX',4)


class ArchiveProvider(unittest.TestCase):
    def setUp(self):
        base=Path(tempfile.gettempdir()).resolve()
        self.root=base/('tt-archive-test-'+uuid.uuid4().hex);self.root.mkdir()
        def cleanup():
            resolved=self.root.resolve()
            if resolved.parent!=base or not resolved.name.startswith('tt-archive-test-'):
                raise RuntimeError('Unexpected test cleanup target')
            shutil.rmtree(resolved)
        self.addCleanup(cleanup)
        self.game=self.root/'game';self.game.mkdir()
        self.dat=self.game/'GAME.DAT';archive(self.dat)

    def provider(self):
        return open_assets(self.game,'LB3',self.root/'cache')

    def test_installed_folder_extracts_requested_asset(self):
        original=self.dat.read_bytes();provider=self.provider()
        self.assertIsInstance(provider,ArchiveAssetIndex)
        path=provider.find('sample',extension='.CD')
        self.assertEqual(path.read_bytes(),b'abc');self.assertEqual(self.dat.read_bytes(),original)
        self.assertTrue(path.is_relative_to(self.root/'cache'))
        self.assertEqual(provider.get_info()['extracted_files'],1)

    def test_cache_digest_detects_same_size_change(self):
        provider=self.provider();path=provider.find('SAMPLE.CD');path.write_bytes(b'xyz')
        with self.assertRaisesRegex(FormatError,'modified or damaged'):provider.find('SAMPLE.CD')

    def test_cached_file_reused(self):
        p=self.provider();one=p.find('SAMPLE.CD');two=p.find('sample.cd')
        self.assertEqual(one,two);self.assertEqual(len(p.events),1)

    def test_path_traversal_rejected(self):
        with self.assertRaises(FormatError):self.provider().find('../SAMPLE.CD')

    def test_reserved_paths_rejected(self):
        provider=self.provider()
        for value in ('NUL.CD','folder/COM1.GHG','folder/name.','C:/foo.CD','foo:stream.CD'):
            with self.subTest(value=value), self.assertRaises(FormatError):provider.find(value)

    def test_archive_path_traversal_rejected(self):
        archive(self.dat,name='../SAMPLE.CD')
        with self.assertRaises(FormatError):self.provider()

    def test_cache_inside_install_rejected(self):
        with self.assertRaises(FormatError):open_assets(self.game,'LB3',self.game/'cache')

    def test_conflicting_archive_resources_rejected(self):
        archive(self.game/'GAME0.DAT',b'xyz')
        with self.assertRaisesRegex(FormatError,'Ambiguous'):self.provider().find('SAMPLE.CD')

    def test_missing_optional_resource(self):
        self.assertIsNone(self.provider().find('ABSENT.CD',required=False))

    def test_exact_lookup_rejects_wrong_directory(self):
        provider=self.provider()
        self.assertEqual(provider.find_exact('sample.cd').read_bytes(),b'abc')
        self.assertIsNone(provider.find_exact('wrong/sample.cd',required=False))
        with self.assertRaises(FormatError):provider.find_exact('wrong/sample.cd')

    def test_index_overlap_rejected(self):
        data=bytearray(self.dat.read_bytes());at=struct.unpack_from('<I',data)[0]
        struct.pack_into('<I',data,at+8+4,999)
        self.dat.write_bytes(data)
        with self.assertRaises(FormatError):index_v6(self.dat)

    def test_extracted_folder_uses_existing_provider(self):
        self.assertIsInstance(open_assets(self.root,'LB3',self.root/'cache'),AssetIndex)


if __name__=='__main__':unittest.main()
