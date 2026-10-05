"""Small, asset-free bounds and command checks for the observed FUSE reader."""
import io
import struct
import unittest
from fuse import decompress, read_entry


class FuseChecks(unittest.TestCase):
    def test_literal_commands(self):
        self.assertEqual(decompress(b'\xe0ABCD\xfdE\xfeFG\xffHIJ',10), b'ABCDEFGHIJ')

    def test_history_and_overlapping_copies(self):
        for encoded, expected in ((b'\xfdA\x00\x00',b'AAAA'),
                                  (b'\xe0ABCD\x80\x00\x03',b'ABCDABCD'),
                                  (b'\xe0ABCD\xc0\x00\x03\x00',b'ABCDABCDA')):
            with self.subTest(encoded=encoded):
                self.assertEqual(decompress(encoded,len(expected)),expected)

    def test_invalid_commands_and_size(self):
        for data,size in ((b'\xe0ABC',4),(b'\x00\x00',3),(b'\xfdA',2),
                          (b'\xfdA',0),(b'',-1),(b'',128*1024*1024+1)):
            with self.subTest(data=data,size=size),self.assertRaises(ValueError):
                decompress(data,size)

    def test_raw_flags_and_compressed_entry(self):
        for flags in (0,12):
            self.assertEqual(read_entry(io.BytesIO(b'xxABCD'),dict(offset=2,packed=4<<5|flags),0,6),b'ABCD')
        encoded=b'\xfdA\x00\x00'
        stream=io.BytesIO(b'xx123'+struct.pack('<I',len(encoded))+encoded)
        self.assertEqual(read_entry(stream,dict(offset=3,packed=4<<5|13),2,11),b'AAAA')

    def test_bounds_unknown_flags_and_truncation(self):
        for row,base,size in ((dict(offset=1,packed=0),0,0),(dict(offset=0,packed=-32),0,10),
                             (dict(offset=-1,packed=0),0,5),(dict(offset=0,packed=32|7),0,5),
                             (dict(offset=2,packed=4<<5),0,5),(dict(offset=0,packed=4<<5),0,9),
                             (dict(offset=0,packed=4<<5|13),0,2),(dict(offset=0,packed=0),-1,2)):
            with self.subTest(row=row,base=base,size=size),self.assertRaises(ValueError):
                read_entry(io.BytesIO(b'abc'),row,base,size)


if __name__=='__main__':unittest.main()
