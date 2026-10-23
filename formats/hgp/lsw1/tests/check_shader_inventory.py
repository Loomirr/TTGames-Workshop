"""Shader extent regressions: metadata and constants may contain END values."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from inspect_native_shaders import shader_end


def words(*values):return struct.pack('<'+'I'*len(values),*values)


class ShaderExtents(unittest.TestCase):
    def test_end_inside_comment_is_not_shader_end(self):
        data=words(0xffff0200,0x0003fffe,0x42415443,0x0000ffff,7,0x02000001,0x800f0000,0x90e40000,0xffff)
        self.assertEqual(shader_end(data,0),len(data))

    def test_end_inside_constant_operand_is_not_shader_end(self):
        data=words(0xfffe0200,0x05000051,0xa00f0000,0xffff,0,0,0,0xffff)
        self.assertEqual(shader_end(data,0),len(data))

    def test_truncated_comments_instructions_and_limits(self):
        for data in (words(0xffff0200,0x0005fffe,0xffff), words(0xffff0200,0x05000051,0xffff),
                     words(0xffff0200,0x80000001,0xffff), words(0,0xffff)):
            self.assertIsNone(shader_end(data,0))
        self.assertIsNone(shader_end(words(0xffff0200,0,0xffff),0,limit=8))
        self.assertIsNone(shader_end(b'abc',0))
        self.assertIsNone(shader_end(b'',-1))

    def test_nonzero_offset_and_next_program_are_separate(self):
        data=b'prefix!'+words(0xffff0300,0,0xffff)+words(0xffff0200,0xffff)
        self.assertEqual(shader_end(data,7),19)


if __name__=='__main__':unittest.main()
