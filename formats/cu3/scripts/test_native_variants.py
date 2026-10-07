"""Constructed counted HGOL variant routing; original assets are not included."""
import copy
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

package = types.ModuleType('native_variant_fixture')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from native_variant_fixture.cu3 import FormatError
from native_variant_fixture.skeleton import scan_skeleton_candidates, select_skeleton, skeleton_identity
from native_variant_fixture.skeleton_diagnostics import skeleton_candidate_report

I4 = (1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)


def hgol(version, special):
    typed = version != 10
    def array(count):
        return (b'ROTV' if typed else b'') + struct.pack('>I',count)
    def label(text, offset):
        return struct.pack('>H',len(text)+1)+text.encode()+b'\0' if version>=15 else struct.pack('>I',offset)
    raw = b'LOGH'+struct.pack('>I',version)+array(1)+label('Root',0)
    raw += struct.pack('>16f3f2B',*I4,0,0,0,255,0)
    raw += (array(1)+struct.pack('>16f',*I4))*2
    raw += array(0)*3+struct.pack('>I',0)
    raw += array(1)+struct.pack('>BBHB',0,0,special,0)
    raw += array(1)+label('Layer',5)+struct.pack('>3H',0,1,0)
    return raw


def trailer(version, threshold, mapping):
    typed = version != 10
    def array(count):
        return (b'ROTV' if typed else b'')+struct.pack('>I',count)
    raw = array(0)+bytes(8)+struct.pack('>6f',-1,-1,-1,1,1,1)+bytes(12)+struct.pack('>f',threshold)
    raw += array(1)+b'\0'
    if version in (10,12):
        raw += array(1)+b'\0'+struct.pack('>f',1)
    return (raw+array(len(mapping))+b''.join(struct.pack('>H',v) for v in mapping)+b'\0'
            +(b'\x23\xc7\x47\x81\0' if version==17 else b''))


def native_group(version=16, base_index=0, count=2):
    raw = b''
    if version in (10,12):
        names = b'Root\0Layer\0'
        raw = b'LBTN'+struct.pack('>2I',1,len(names))+names
    raw += b'5LVI'+struct.pack('>2I',1,0)+b'ROTV'+struct.pack('>I',count)
    for index in range(count):
        base = index == base_index
        raw += hgol(version,index)+trailer(version,0 if base else 25,[] if base else [0])
    return raw+bytes(4)+(b'\1' if version in (10,12) else b'')+b'ATEM'


def associations():
    display = dict(version=32,specials=[dict(index=i,name='Body',parts=[dict(part=i,material=0)],unsupported_commands=[])
                                      for i in range(2)])
    mesh = dict(parts=[dict(vertices=[dict(weights=[(0,1.)])]) for _ in range(2)])
    return display,mesh


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'fixture.ghg'
        self.display,self.mesh = associations()

    def scan(self, raw=None):
        self.path.write_bytes(native_group() if raw is None else raw)
        return scan_skeleton_candidates(self.path)

    def select(self, scan, **kwargs):
        return select_skeleton(scan['candidates'],display=self.display,mesh=self.mesh,**kwargs)

    def test_counted_hgol10_and16_choose_explicit_base(self):
        for version in (10,12,16,17):
            with self.subTest(version=version):
                scan=self.scan(native_group(version))
                selected=self.select(scan)
                self.assertEqual(selected['selection']['reason'],'verified_native_variant_base')
                self.assertEqual(selected['hgol_offset'],scan['candidates'][0]['hgol_offset'])
                self.assertEqual(scan['candidates'][0]['native_variant']['end_offset'],scan['candidates'][1]['hgol_offset'])

    def test_selection_is_not_first_record_order(self):
        scan=self.scan(native_group(base_index=1))
        self.assertEqual(self.select(scan)['hgol_offset'],scan['candidates'][1]['hgol_offset'])

    def test_mesh_and_display_required_for_multirig_proof(self):
        scan=self.scan()
        with self.assertRaisesRegex(FormatError,'requires decoded mesh'):
            select_skeleton(scan['candidates'],display=self.display)

    def test_count_does_not_override_native_base(self):
        scan=self.scan()
        base=scan['candidates'][0]
        child=copy.deepcopy(base['joints'][0]);child.update(index=1,name='Child',parent=0)
        base['joints'].append(child)
        base['native_variant']['joint_map']=[0,1]
        with self.assertRaisesRegex(FormatError,'selected before count validation'):
            self.select(scan,expected_nodes=1)

    def test_retained_identity_cannot_hide_bad_variant(self):
        scan=self.scan();identity=skeleton_identity(scan['candidates'][0])
        scan['candidates'][1]['native_variant']['metadata_map']=[4]
        with self.assertRaisesRegex(FormatError,'outside its table'):
            self.select(scan,identity=identity)

    def test_explicit_retained_variant_identity_after_whole_group_validation(self):
        scan=self.scan();identity=skeleton_identity(scan['candidates'][1])
        selected=self.select(scan,identity=identity)
        self.assertEqual(selected['hgol_offset'],scan['candidates'][1]['hgol_offset'])
        self.assertEqual(selected['selection']['reason'],'retained_native_variant_identity')

    def test_changed_wrapper_is_part_of_retained_ownership(self):
        scan=self.scan();before=skeleton_identity(scan['candidates'][0])
        scan['candidates'][0]['native_variant_group']['serialized_sha256']='changed'
        self.assertNotEqual(before,skeleton_identity(scan['candidates'][0]))

    def test_count_mismatch_unowned_marker_and_nested_interpretations_rejected(self):
        raw=native_group();start=raw.index(b'LOGH')
        changed=bytearray(raw);struct.pack_into('>I',changed,start-4,3)
        for case in (bytes(changed),raw+hgol(16,0),raw+b'LOGH'+struct.pack('>I',999)):
            with self.subTest(length=len(case)),self.assertRaises(FormatError):
                self.select(self.scan(case))

    def test_nested_hgol_inside_opaque_payload_is_not_suppressed(self):
        raw=native_group();scan=self.scan(raw)
        opaque=next(s for s in scan['candidates'][0]['decoded_section_spans'] if s['field']=='opaque_length')['start']
        child=hgol(16,0)
        changed=raw[:opaque]+struct.pack('>I',len(child))+child+raw[opaque+4:]
        scan=self.scan(changed)
        self.assertEqual(len(scan['candidates']),3)
        with self.assertRaisesRegex(FormatError,'count does not cover'):
            self.select(scan)

    def test_unique_unsupported_trailer_version_preserves_existing_single_rig_path(self):
        raw=b'5LVI'+struct.pack('>2I',1,0)+b'ROTV'+struct.pack('>I',1)+hgol(17,0)
        selected=self.select(self.scan(raw))
        self.assertEqual(selected['version'],17)
        self.assertEqual(selected['selection']['reason'],'unique_compatible_table')

    def test_different_native_bind_value_is_preserved_not_normalized(self):
        scan=self.scan()
        other=scan['candidates'][1]['joints'][0]['local_bind_row_major']
        other[8]=1e-6
        before=copy.deepcopy(other)
        selected=self.select(scan)
        self.assertEqual(other,before)
        self.assertEqual(selected['joints'][0]['local_bind_row_major'][8],0)
        self.assertNotEqual(skeleton_identity(selected)['binding_sha256'],
                            skeleton_identity(scan['candidates'][1])['binding_sha256'])

    def test_duplicate_name_table_interpretation_rejected(self):
        raw=native_group(10)
        names=b'Root\0Layer\0'
        raw+=b'LBTN'+struct.pack('>2I',1,len(names))+names
        with self.assertRaisesRegex(FormatError,'count|interpretation'):
            self.select(self.scan(raw))

    def test_unknown_group_version_rejected(self):
        with self.assertRaisesRegex(FormatError,'HGOL 10, 12, 16 or 17'):
            self.select(self.scan(native_group(15)))

    def test_truncated_and_unknown_trailers_rejected(self):
        raw=native_group();scan=self.scan(raw)
        offset=scan['candidates'][0]['end_offset']
        altered=bytearray(raw);altered[offset:offset+4]=b'NOPE'
        for case in (raw[:-1],raw[:offset+12],bytes(altered)):
            with self.subTest(length=len(case)),self.assertRaises(FormatError):
                self.select(self.scan(case))

    def test_nonzero_auxiliary_field_and_terminal_byte_rejected(self):
        raw=native_group();scan=self.scan(raw);end=scan['candidates'][0]['native_variant']['end_offset']
        for offset in (scan['candidates'][0]['end_offset']+11,end-1):
            changed=bytearray(raw);changed[offset]=1
            with self.subTest(offset=offset),self.assertRaises(FormatError):
                self.select(self.scan(bytes(changed)))

    def test_duplicate_or_missing_zero_threshold_rejected(self):
        for first,second in ((0,0),(1,25)):
            scan=self.scan()
            scan['candidates'][0]['native_variant']['threshold']=first
            scan['candidates'][1]['native_variant']['threshold']=second
            with self.subTest(values=(first,second)),self.assertRaises(FormatError):self.select(scan)

    def test_joint_map_bounds_and_names_rejected(self):
        scan=self.scan();scan['candidates'][1]['native_variant']['joint_map']=[1]
        with self.assertRaisesRegex(FormatError,'outside the base rig'):self.select(scan)
        scan=self.scan();scan['candidates'][1]['joints'][0]['name']='Other'
        with self.assertRaisesRegex(FormatError,'names or retained hierarchy'):self.select(scan)

    def test_root_sized_metadata_map_required(self):
        scan=self.scan();scan['candidates'][1]['native_variant']['metadata_map']=[]
        with self.assertRaisesRegex(FormatError,'full base metadata'):self.select(scan)

    def test_explicit_remap_allows_native_lod_draw_names(self):
        scan=self.scan();self.display['specials'][1]['name']='Wrong'
        self.assertEqual(self.select(scan)['hgol_offset'],scan['candidates'][0]['hgol_offset'])
        self.display,self.mesh=associations()
        scan=self.scan();scan['candidates'][1]['layer_metadata'][0]['joint']=2
        with self.assertRaisesRegex(FormatError,'rigid ownership|rigid joint'):self.select(scan)

    def test_morph_skin_can_map_to_a_rigid_face_lod(self):
        scan=self.scan();base=scan['candidates'][0]
        base['layer_metadata'][0].update(kind=3,joint=255)
        base['layers'][0].update(rigids=0,skins=1)
        self.assertEqual(self.select(scan)['hgol_offset'],base['hgol_offset'])
        self.mesh['parts'][0]['vertices'][0]['weights']=[(8,1.)]
        with self.assertRaisesRegex(FormatError,'skin palette'):self.select(scan)

    def test_hgol17_extension_flag_and_boundary_checked(self):
        raw=native_group(17);scan=self.scan(raw)
        end=scan['candidates'][0]['native_variant']['end_offset']
        with self.assertRaisesRegex(FormatError,'extension flag'):
            self.select(self.scan(raw[:end-1]+b'\1'+raw[end:]))
        with self.assertRaises(FormatError):
            self.select(self.scan(raw[:end-2]+raw[end:]))

    def test_complete_disjoint_special_and_part_coverage_required(self):
        scan=self.scan();scan['candidates'][1]['layer_metadata'][0]['special']=0
        with self.assertRaisesRegex(FormatError,'overlaps'):self.select(scan)
        scan=self.scan();self.mesh['parts'].append(dict(vertices=[]))
        with self.assertRaisesRegex(FormatError,'complete model display/geometry'):self.select(scan)

    def test_skin_weights_validated_against_own_variant(self):
        scan=self.scan()
        for candidate in scan['candidates']:
            candidate['layer_metadata'][0]['kind']=1
            candidate['layers'][0].update(rigids=0,skins=1)
        self.mesh['parts'][1]['vertices'][0]['weights']=[(1,1.)]
        with self.assertRaisesRegex(FormatError,'skin palette'):self.select(scan)

    def test_native_cross_layer_remap_and_omission_are_preserved(self):
        scan=self.scan();base,variant=scan['candidates']
        for candidate in scan['candidates']:
            candidate['layers'].append(dict(name='Second',metadata_index=1,rigids=0,skins=0))
        variant['layers'][0].update(rigids=0)
        variant['layers'][1].update(metadata_index=0,rigids=1)
        variant['layer_metadata'][0]['layer']=1
        selected=self.select(scan)
        cross=selected['selection']['native_variant_group']['cross_layer_remaps']
        self.assertEqual([(r['base_layer'],r['variant_layer']) for r in cross],[(0,1)])
        variant['native_variant']['metadata_map']=[65535]
        selected=self.select(scan)
        omissions=selected['selection']['native_variant_group']['remap_omissions']
        self.assertEqual(omissions[0]['omitted_base_entries'],1)
        self.assertEqual(omissions[0]['unmapped_variant_entries'],[0])

    def test_diagnostics_selects_same_base_and_exposes_routing_without_raw_bytes(self):
        scan=self.scan()
        report=skeleton_candidate_report(scan,display=self.display,mesh=self.mesh)
        self.assertEqual(report['selection']['outcome'],'selected')
        self.assertEqual(report['selection']['reason'],'verified_native_variant_base')
        self.assertEqual(report['selection']['native_variant_group']['count'],2)
        self.assertNotIn('joint_map',report['candidates'][0]['native_variant'])

    def test_diagnostic_limits_bound_nested_variant_relationships_without_changing_selection(self):
        scan=self.scan(native_group(count=3))
        self.display['specials']=[dict(index=i,name='Body',parts=[dict(part=i,material=0)],unsupported_commands=[])
                                  for i in range(12)]
        self.mesh['parts']=[dict(vertices=[dict(weights=[(0,1.)])]) for _ in range(12)]
        for index,candidate in enumerate(scan['candidates']):
            candidate['layer_metadata']=[dict(kind=0,joint=0,special=index*4+i,layer=min(index,1)) for i in range(4)]
            candidate['layers']=[dict(name='Layer',metadata_index=0,rigids=4 if index==0 else 0,skins=0),
                                 dict(name='Second',metadata_index=4 if index==0 else 0,rigids=0 if index==0 else 4,skins=0)]
            if index:
                candidate['native_variant']['metadata_map']=[0,1,65535,65535]
        report=skeleton_candidate_report(scan,display=self.display,mesh=self.mesh,
                                         max_candidates=1,max_relationships=1,max_differences=1)
        self.assertEqual(report['selection']['outcome'],'selected')
        native=report['selection']['native_variant_group']
        self.assertEqual((len(native['candidate_offsets']),native['candidate_offsets_total'],native['omitted_candidate_offsets']),(1,3,2))
        self.assertEqual((len(native['cross_layer_remaps']),native['cross_layer_remaps_total'],native['omitted_cross_layer_remaps']),(1,4,3))
        self.assertEqual((len(native['remap_omissions']),native['remap_omissions_total'],native['omitted_remap_omissions']),(1,2,1))
        row=native['remap_omissions'][0]
        self.assertEqual((row['unmapped_variant_entries'],row['unmapped_variant_entries_total'],row['omitted_unmapped_variant_entries']),([2],2,1))
        full=scan['candidates'][0]['selection']['native_variant_group']
        self.assertEqual(len(full['cross_layer_remaps']),4)
        self.assertEqual(full['remap_omissions'][0]['unmapped_variant_entries'],[2,3])


if __name__=='__main__':
    unittest.main()
