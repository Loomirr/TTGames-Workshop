"""Asset-free PICA pixel/bounds and stored-mip checks; requires Pillow."""
import io
import struct
import unittest
from PIL import Image
from pica_texture import decode, etc_block
from btga_to_dds import levels_from_btga, dds


def btga(payload,width=8,height=8,fmt=0,mips=1):
    header=bytearray(56);header[:12]=bytes.fromhex('0004000010000000f2ffffff')
    struct.pack_into('<IHHIII',header,20,len(payload),width,height,len(payload),fmt,mips)
    return bytes(header)+payload


class TextureChecks(unittest.TestCase):
    def test_raw_formats_known_pixels(self):
        cases={0:(bytes([255,30,20,10])*64,(10,20,30,255)),
               1:(bytes([30,20,10])*64,(10,20,30,255)),
               2:(struct.pack('<H',31<<11|16<<6|7<<1|1)*64,(255,132,58,255)),
               3:(struct.pack('<H',31<<11|63<<5|3)*64,(255,255,24,255)),
               4:(struct.pack('<H',0x1234)*64,(17,34,51,68)),
               5:(bytes([7,50])*64,(50,50,50,7)),6:(bytes([70,80])*64,(80,70,0,255)),
               7:(bytes([60])*64,(60,60,60,255)),8:(bytes([40])*64,(0,0,0,40)),
               9:(bytes([0xab])*64,(170,170,170,187)),10:(bytes([0x55])*32,(85,85,85,255)),
               11:(bytes([0x77])*32,(0,0,0,119))}
        for fmt,(payload,expected) in cases.items():
            with self.subTest(fmt=fmt):
                self.assertEqual(decode(payload,8,8,fmt).tobytes(),bytes(expected)*64)

    def test_etc1_and_alpha(self):
        self.assertEqual(decode(bytes(32),8,8,12).tobytes(),bytes([2,2,2,255])*64)
        payload=(struct.pack('<Q',0x8888888888888888)+bytes(8))*4
        self.assertEqual(decode(payload,8,8,13).tobytes(),bytes([2,2,2,136])*64)
        with self.assertRaises(ValueError):etc_block(1<<33|4<<56)

    def test_tile_order_and_vertical_flip(self):
        payload=b''.join(bytes([255,0,0,i]) for i in range(64))
        image=decode(payload,8,8,0,flip_y=True)
        for xy,value in (((0,7),0),((1,7),1),((0,6),2),((1,6),3)):
            self.assertEqual(image.getpixel(xy),(value,0,0,255))

    def test_reject_short_long_unknown_and_bad_dimensions(self):
        for payload,w,h,fmt in ((b'',8,8,0),(bytes(257),8,8,0),(bytes(31),8,8,12),
                                 (bytes(63),8,8,13),(bytes(256),8,8,14),(b'',4,8,0),
                                 (b'',9,8,0),(b'',8200,8,0)):
            with self.subTest(fmt=fmt,w=w,h=h),self.assertRaises(ValueError):decode(payload,w,h,fmt)

    def test_subtile_mips_remain_rejected(self):
        payload=bytes([255,30,20,10])*(16*8)+bytes([128,60,50,40])*64
        with self.assertRaisesRegex(ValueError,'sub-tile'):
            levels_from_btga(btga(payload,16,8,0,2))

    def test_valid_mips_dds_and_header_rejection(self):
        payload=bytes([255,30,20,10])*(16*16)+bytes([128,60,50,40])*64
        levels,fmt=levels_from_btga(btga(payload,16,16,0,2))
        self.assertEqual([im.size for im in levels],[(16,16),(8,8)])
        encoded=dds(levels);image=Image.open(io.BytesIO(encoded)).convert('RGBA')
        self.assertEqual(image.tobytes(),levels[0].tobytes())
        self.assertEqual(struct.unpack_from('<I',encoded,28)[0],2)
        for raw in (b'bad',btga(bytes(256),fmt=99),btga(bytes(256),mips=2),
                    btga(bytes(256))+b'x',btga(bytes(256),width=4,height=16)):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):levels_from_btga(raw)


if __name__=='__main__':unittest.main()
