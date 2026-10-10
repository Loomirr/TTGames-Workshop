"""Independent parameter-span fixtures; no game inputs or shader assumptions."""
import math
import struct
import unittest
from material_parameter_inspection import inspect_parameters


def fixture():
    raw = bytearray(512)
    start = 12
    struct.pack_into('>I', raw, start, 13)
    for i in range(13):
        struct.pack_into('>I', raw, start+4+i*4, 4)
        struct.pack_into('>f', raw, start+56+i*4, -.25)
        struct.pack_into('>I', raw, start+108+i*4, 0xffffffff)
    struct.pack_into('>3f', raw, start+265, 3, .5, 1)
    struct.pack_into('>f', raw, start+393, .125)
    return raw, dict(texture_end=start, name_offset=start+492, table_version=177)


class ParameterTests(unittest.TestCase):
    def test_observed_span_and_absolute_offsets(self):
        raw, entry = fixture();before=bytes(raw)
        for version in (176,177):
            entry['table_version']=version;report=inspect_parameters(raw,entry)
            self.assertEqual(report['status'],'observed_layout_decoded')
            self.assertEqual(report['constants']['normal_layer_scale'],dict(offset=277,values=[3,.5,1]))
            self.assertEqual(report['constants']['brdf_roughness']['values'],[.125])
            self.assertEqual(report['samplers'][12]['mipmap_bias'],-.25)
        self.assertEqual(bytes(raw),before)

    def test_later_and_unknown_versions_are_not_reinterpreted(self):
        raw,entry=fixture()
        for version in (163,174,191,196,202,229,232,234,235,999):
            entry['table_version']=version;report=inspect_parameters(raw,entry)
            self.assertEqual(report['status'],'unverified_layout');self.assertNotIn('constants',report)

    def test_wrong_count_and_span_remain_opaque(self):
        raw,entry=fixture();struct.pack_into('>I',raw,12,16)
        self.assertEqual(inspect_parameters(raw,entry)['status'],'unverified_layout')
        raw,entry=fixture();entry['name_offset']-=1
        self.assertEqual(inspect_parameters(raw,entry)['status'],'unverified_layout')

    def test_invalid_sampler_and_flip(self):
        for offset,value,fmt in ((4,17,'I'),(56,math.nan,'f'),(264,2,'B')):
            raw,entry=fixture();struct.pack_into('>'+fmt,raw,12+offset,value)
            report=inspect_parameters(raw,entry)
            self.assertEqual(report['status'],'unverified_layout');self.assertNotIn('constants',report)

    def test_nonfinite_constant_is_not_published_as_decoded(self):
        raw,entry=fixture();struct.pack_into('>f',raw,12+393,math.inf)
        report=inspect_parameters(raw,entry)
        self.assertEqual(report['status'],'unverified_layout');self.assertNotIn('constants',report)

    def test_invalid_source_bounds_rejected(self):
        raw,entry=fixture()
        for start,end in ((-1,100),(0,600),(100,0)):
            entry.update(texture_end=start,name_offset=end)
            with self.assertRaises(ValueError):inspect_parameters(raw,entry)


if __name__=='__main__':unittest.main()
