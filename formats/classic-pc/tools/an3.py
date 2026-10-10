"""Inspect classic PC AN3 scalar tracks. No skeleton binding or native writer.

Uses the contributor's CU2 curve reader for the shared little-endian blocks.
The observed unrelocated TCS 5INA wrapper is normalized only in memory.
AN4 containers must use Workshop's separate, version-gated AN4 readers.
"""
import argparse
import struct
from cu2 import Block
from reader_bounds import read_file, span


class An3(Block):
    def __init__(self, path, data=None):
        data = read_file(path) if data is None else bytes(data)
        tag = data[:4]
        if data[4:8] == b'5INA':
            span(data,0,64,'unrelocated AN3 header')
            table = struct.unpack_from('<I',data,0)[0]
            span(data,table,4,'AN3 fixup table')
            count = struct.unpack_from('<I',data,table)[0]
            if count > 64:raise ValueError('Unverified AN3 fixup count')
            span(data,table+4,count*4,'AN3 fixup records')
            d = bytearray(data[4:]);tag=b'5INA'
            for at in (24,36,40,44,48,52,56):
                relative=struct.unpack_from('<I',d,at)[0]
                if relative:
                    resolved=relative+at
                    span(d,resolved,1,'AN3 relative pointer')
                    struct.pack_into('<I',d,at,resolved)
            # Explicit 5INA wrapper has the observed shared scalar layout.
            d[:4]=b'4INA'
            data=bytes(d)
        elif tag not in (b'4INA',b'6INA',b'8INA'):
            raise ValueError(f'Unverified classic AN3 tag {tag!r}; AN4 is a separate format')
        super().__init__(data,0)
        self.tag=tag
        if self.channels != 9 or any(k < 16 and k != 6 for k in self.key_types):
            raise ValueError('Unverified standalone AN3 channels/key types')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    args=parser.parse_args(argv)
    try:
        clip=An3(args.source)
        for frame in (0,clip.frames//2,clip.frames-1):clip.pose(frame)
    except (OSError,ValueError,struct.error) as error:parser.error(str(error))
    print(f'{clip.tag.decode()}: {clip.nodes} nodes, {clip.frames} frames, {clip.channels} scalar channels/node')
    print('No skeleton ownership or pose fidelity is established by this inspection.')


if __name__=='__main__':main()
