"""Portable resource/renderer/ownership regressions; only constructed fixtures."""
from copy import deepcopy
from pathlib import Path
import hashlib
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('identity_fixture')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from identity_fixture.cu3 import FormatError
from identity_fixture.asset_index import AssetIndex
from identity_fixture.dependencies import ResourceResolver, dependency_report
from identity_fixture.profiles import character_profile, profile_identity
from identity_fixture.resource_identity import model_resource_identity
from identity_fixture.skeleton import read_skeleton, skeleton_identity, select_skeleton, attachment_locator
from identity_fixture.animation_catalog import catalog
from identity_fixture.animation_ownership import attachment_tracks

I4 = (1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)


def native_skeleton(*, name='Root', translation=0, special=0, metadata_kind=0):
    """One HGOL16 with native transform, locator and layer tables."""
    encoded = name.encode('ascii') + b'\0'
    local = list(I4)
    local[12] = translation
    joint = struct.pack('>H', len(encoded)) + encoded + struct.pack('>16f3f2B', *I4, 0, 0, 0, 255, 0)
    data = b'LOGH' + struct.pack('>I',16) + b'ROTV' + struct.pack('>I',1) + joint
    data += b'ROTV' + struct.pack('>I16f',1,*local)
    data += b'ROTV' + struct.pack('>I16f',1,*I4)
    data += b'ROTV' + struct.pack('>I',0)  # pre-locator bytes
    data += b'ROTV' + struct.pack('>I',0)  # locators
    data += b'ROTV' + struct.pack('>I',0)  # locator remap
    data += struct.pack('>I',0)          # opaque payload
    data += b'ROTV' + struct.pack('>IBBHB',1,metadata_kind,0,special,0)
    data += b'ROTV' + struct.pack('>IH',1,6) + b'Layer\0' + struct.pack('>3H',0,1,0)
    return data


def bank(members):
    count = len(members)
    table_end = 24 + 28 * count
    names = b''.join(name.encode('ascii') + b'\0' for name in members)
    start = table_end + len(names)
    total = start + count * 3
    data = struct.pack('<6I',0x1234567A,count,total,0,0,0)
    name_offset = table_end
    for index,name in enumerate(members):
        data += struct.pack('<7I',name_offset,start+3*index,3,0,0,0,0)
        name_offset += len(name)+1
    return data + names + b'xyz' * count


def native_skeleton_v10():
    names=b'Root\0Layer\0'
    data=b'LBTN'+struct.pack('>2I',1,len(names))+names
    data+=b'LOGH'+struct.pack('>3I',10,1,0)
    data+=struct.pack('>16f3f2B',*I4,0,0,0,255,0)
    data+=struct.pack('>I16f',1,*I4)*2
    data+=struct.pack('>4I',0,0,0,0)
    data+=struct.pack('>IBBHB',1,0,0,0,0)
    data+=struct.pack('>2I3H',1,5,0,1,0)
    return data


def definition(model, attachments=(), textures=()):
    objects = [{'class':'Character Attachment','fields':{'Layer':1,'Resource File':name},'complete':True}
               for name in attachments]
    objects += [{'class':'Texture','fields':{'Texture File':name},'complete':True} for name in textures]
    return {'character':{'Skeleton Name':model,'Use Default Layers':2,'Default Layers':2},'objects':objects}


class SkeletonOwnershipTests(unittest.TestCase):
    def read(self, raw, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fixture.GHG'
            path.write_bytes(raw)
            return read_skeleton(path, **kwargs)

    def test_identical_duplicate_tables_preserve_all_offsets(self):
        raw = native_skeleton()
        rig = self.read(raw + raw, expected_nodes=1)
        self.assertEqual(rig['candidate_offsets'],[0,len(raw)])
        self.assertEqual(rig['selection']['reason'],'identical_duplicate_tables')
        self.assertEqual(rig['byte_order'],'big')

    def test_equal_counts_names_and_labels_do_not_hide_conflicting_bind(self):
        first = native_skeleton()
        with self.assertRaisesRegex(FormatError,'conflicting native bind tables') as caught:
            self.read(first + native_skeleton(translation=4),expected_nodes=1)
        self.assertIn('0x0',str(caught.exception))
        self.assertIn(hex(len(first)),str(caught.exception))

    def test_identical_bind_different_layer_ownership_is_ambiguous(self):
        with self.assertRaisesRegex(FormatError,'conflicting resource/layer ownership'):
            self.read(native_skeleton() + native_skeleton(special=1))

    def test_display_ownership_can_identify_one_candidate(self):
        first = native_skeleton(special=7)
        rig = self.read(first + native_skeleton(),display={'specials':[{}]})
        self.assertEqual(rig['hgol_offset'],len(first))
        self.assertTrue(rig['selection']['display_ownership_checked'])
        self.assertEqual(rig['selection']['rejected_candidates'][0]['offset'],0)

    def test_display_compatibility_alone_does_not_pick_between_two_bind_tables(self):
        with self.assertRaisesRegex(FormatError,'Ambiguous GHG skeleton'):
            self.read(native_skeleton() + native_skeleton(translation=1),display={'specials':[{}]})

    def test_retained_full_identity_disambiguates_without_using_offsets(self):
        identity = self.read(native_skeleton(translation=2))['identity']
        first = native_skeleton()
        rig = self.read(first + native_skeleton(translation=2),identity=identity)
        self.assertEqual(rig['hgol_offset'],len(first))
        self.assertEqual(rig['identity'],identity)
        identity['ownership_sha256']='0'*64
        with self.assertRaisesRegex(FormatError,'retained native skeleton identity'):
            self.read(first,identity=identity)

    def test_trailing_false_marker_is_a_diagnostic_not_an_out_of_bounds_read(self):
        rig = self.read(native_skeleton()+b'LOGH')
        self.assertEqual(rig['hgol_offset'],0)
        self.assertTrue(rig['selection']['rejected_candidates'])

    def test_truncated_layer_tail_is_rejected(self):
        with self.assertRaises(FormatError):
            self.read(native_skeleton()[:-1])

    def test_bad_orientation_is_not_accepted_as_identity(self):
        raw=bytearray(native_skeleton())
        struct.pack_into('>f',raw,23,float('nan'))
        with self.assertRaisesRegex(FormatError,'non-finite'):
            self.read(raw)

    def test_joint_count_is_a_validation_not_an_ownership_selector(self):
        first=self.read(native_skeleton())
        second=deepcopy(first)
        second['hgol_offset']=999
        joint=deepcopy(second['joints'][0])
        joint.update(index=1,name='Child',parent=0)
        second['joints'].append(joint)
        with self.assertRaisesRegex(FormatError,'conflicting native bind tables'):
            select_skeleton([first,second],expected_nodes=1)

    def test_conflicting_name_tables_report_both_resource_candidates(self):
        raw=native_skeleton_v10()
        names=b'Bone\0Layer\0'
        with self.assertRaisesRegex(FormatError,'conflicting native bind tables') as caught:
            self.read(raw+b'LBTN'+struct.pack('>2I',1,len(names))+names)
        self.assertIn('NTBL 0x0',str(caught.exception))
        self.assertIn('NTBL '+hex(len(raw)),str(caught.exception))

    def test_candidate_search_has_an_explicit_budget(self):
        with self.assertRaisesRegex(FormatError,'candidate limit'):
            self.read((b'LOGH'+struct.pack('>I',99))*4097)


class AssetTreeFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def file(self,name,data=b'fixture'):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        return path


class ResourcePathTests(AssetTreeFixture):
    def test_qualified_path_never_falls_back_to_only_basename(self):
        self.file('Real/Hero_DX11.GHG')
        assets=AssetIndex(self.root)
        self.assertIsNone(assets.find('Wrong/Hero','_DX11','.GHG',required=False))
        self.assertEqual(assets.find('real/hero','_DX11','.GHG').relative_to(self.root).as_posix(),'Real/Hero_DX11.GHG')

    def test_identical_payload_does_not_establish_basename_ownership(self):
        self.file('A/Hero_DX11.GHG')
        self.file('B/Hero_DX11.GHG')
        with self.assertRaisesRegex(FormatError,'ambiguous basenames') as caught:
            AssetIndex(self.root).find('Hero','_DX11','.GHG')
        self.assertIn('A/Hero_DX11.GHG',str(caught.exception))
        self.assertIn('B/Hero_DX11.GHG',str(caught.exception))

    def test_case_collision_is_reported_even_for_equal_bytes(self):
        self.file('A/Hero_DX11.GHG')
        self.file('A/HERO_DX11.GHG')
        assets=AssetIndex(self.root)
        if len(assets.files['hero_dx11.ghg'])<2:
            self.skipTest('Fixture requires a case-sensitive filesystem')
        with self.assertRaisesRegex(FormatError,'case-colliding'):
            assets.find_exact('A/Hero_DX11.GHG')

    def test_only_the_active_renderer_closure_is_required(self):
        self.file('Hero.CD')
        self.file('Body_DX11.GHG')
        self.file('Print_DX11.TEX')
        cd=definition('Body',attachments=['Absent_NXG.GSC'],textures=['Absent_NXG.TEX','Print_DX11.TEX'])
        cut=types.SimpleNamespace(version=19,path=Path('scene.CU3'),actors=[{'name':'Instance1_Hero','parent':None,'records':[{}]}])
        with patch('identity_fixture.dependencies.character_definition',return_value=cd):
            report=dependency_report(cut,ResourceResolver(AssetIndex(self.root),'LB3'))
        self.assertEqual(report['resolved_resources'],1)
        self.assertEqual(report['missing_resources'],0)
        self.assertEqual(report['missing_textures'],0)
        self.assertEqual(len(report['resources'][0]['inactive_renderer_references']),2)
        self.assertEqual(report['resources'][0]['textures'][0]['logical_path'],'Print_DX11.TEX')

    def test_explicit_inactive_model_does_not_select_a_different_file(self):
        self.file('Body_NXG_DX11.GHG')
        with self.assertRaisesRegex(FormatError,'inactive renderer'):
            ResourceResolver(AssetIndex(self.root),'LB3').resolve_model('Body_NXG.GHG')

    def test_explicit_static_reference_does_not_choose_same_name_ghg(self):
        self.file('Object_DX11.GHG')
        self.file('Object_DX11.GSC')
        model=ResourceResolver(AssetIndex(self.root),'LB3').resolve_model('Object.GSC')
        self.assertEqual(model.suffix,'.GSC')

    def test_build_remains_unknown_and_disabled_profiles_remain_disabled(self):
        identity=profile_identity('LB3')
        self.assertEqual(identity['renderer'],'DX11')
        self.assertEqual(identity['animation_suffix'],'NXG')
        self.assertIsNone(identity['build'])
        self.assertEqual(identity['structure_byte_orders']['definition'],'little')
        self.assertEqual(identity['structure_byte_orders']['HGOL'],'big')
        for game in ('LOTR','TFA','DCSV','LMSH2','LSW1'):
            with self.assertRaises(FormatError):character_profile(game)

    def test_mismatched_provider_profile_is_rejected(self):
        assets=AssetIndex(self.root)
        assets.profile='LMSH1'
        with self.assertRaisesRegex(FormatError,'different game profile'):
            ResourceResolver(assets,'LB3')

    def test_active_attachment_cycle_is_reported_with_retained_spelling(self):
        self.file('Hero.CD');self.file('Hat.CD')
        self.file('Body_DX11.GHG');self.file('Hat_DX11.GSC')
        definitions={'Hero':definition('Body',attachments=['Hat']),'Hat':definition('Hat',attachments=['Hero'])}
        cut=types.SimpleNamespace(version=19,path=Path('scene.CU3'),actors=[{'name':'Instance1_Hero','parent':None,'records':[{}]}])
        with patch('identity_fixture.dependencies.character_definition',side_effect=lambda path:definitions[path.stem]):
            report=dependency_report(cut,ResourceResolver(AssetIndex(self.root),'LB3'))
        self.assertEqual(report['cycles'],[['Hero','Hat','Hero']])
        self.assertEqual(report['resolved_resources'],2)

    def test_attachment_cycle_is_found_when_both_nodes_are_root_requests(self):
        self.file('Hero.CD');self.file('Hat.CD')
        self.file('Body_DX11.GHG');self.file('Hat_DX11.GSC')
        definitions={'Hero':definition('Body',attachments=['Hat']),'Hat':definition('Hat',attachments=['Hero'])}
        cut=types.SimpleNamespace(version=19,path=Path('scene.CU3'),actors=[
            {'name':'Instance1_'+name,'parent':None,'records':[{}]} for name in ('Hero','Hat')])
        with patch('identity_fixture.dependencies.character_definition',side_effect=lambda path:definitions[path.stem]):
            report=dependency_report(cut,ResourceResolver(AssetIndex(self.root),'LB3'))
        self.assertEqual(report['cycles'],[['Hero','Hat','Hero']])

    def test_optional_store_ambiguity_does_not_change_model_resolution(self):
        self.file('Hero_DX11.GHG')
        self.file('A/Hero_DX11.NXG_TEXTURES')
        self.file('B/Hero_DX11.NXG_TEXTURES')
        cut=types.SimpleNamespace(version=19,path=Path('scene.CU3'),actors=[{'name':'Instance1_Hero','parent':None,'records':[{}]}])
        report=dependency_report(cut,ResourceResolver(AssetIndex(self.root),'LB3'))
        self.assertEqual(report['resolved_resources'],1)
        self.assertIn('Optional texture-store lookup',report['resources'][0]['issues'][0])


class CatalogOwnershipTests(AssetTreeFixture):
    def animation_set(self, name, *, refs=(), files=()):
        self.file(name,b'set')
        objects=[{'class':'Character Anim Set Reference','fields':{'CharAnimSet Name':ref}} for ref in refs]
        objects += [{'class':'Character Anim Entry','fields':{'Action':'Idle','ANI4 Animation File 1':file}} for file in files]
        return {'objects':objects,'source_sha256':hashlib.sha256(b'set').hexdigest(),'version':25}

    def read_catalog(self,sets,root,game='LB3'):
        assets=AssetIndex(self.root)
        assets.profile=game
        roots=root if isinstance(root,list) else [root]
        cd={'objects':[{'class':'Character Anim Set Reference','fields':{'CharAnimSet Name':name}} for name in roots]}
        with patch('identity_fixture.animation_catalog.read_definition',side_effect=lambda path:sets[path.relative_to(self.root).as_posix()]):
            return catalog(assets,cd)

    def test_qualified_clip_path_and_authored_spelling_are_retained(self):
        sets={'Sets/Main.AS':self.animation_set('Sets/Main.AS',files=['Clips/A/Idle'])}
        self.file('Clips/A/Idle_DEF_NXG.AN4')
        self.file('Clips/B/Idle_DEF_NXG.AN4')
        report=self.read_catalog(sets,'Sets/Main')
        entry=report['entries'][0]
        self.assertEqual(entry['source_logical_path'],'Clips/A/Idle_DEF_NXG.AN4')
        self.assertEqual(entry['file_reference'],'Clips/A/Idle')
        self.assertEqual(entry['set_logical_path'],'Sets/Main.AS')
        self.assertEqual(report['issues'],[])

    def test_cycles_are_reported_and_not_reexpanded(self):
        sets={'A.AS':self.animation_set('A.AS',refs=['B']),
              'B.AS':self.animation_set('B.AS',refs=['A'])}
        report=self.read_catalog(sets,'A')
        self.assertEqual(report['sets'],2)
        self.assertEqual(report['cycles'],[['A.AS','B.AS','A.AS']])
        self.assertIn('Cyclic',report['issues'][0])

    def test_shared_root_animation_cycle_is_reported(self):
        sets={'A.AS':self.animation_set('A.AS',refs=['B']),
              'B.AS':self.animation_set('B.AS',refs=['A'])}
        report=self.read_catalog(sets,['A','B'])
        self.assertEqual(report['cycles'],[['A.AS','B.AS','A.AS']])

    def test_animation_graph_limit_stops_discovery_instead_of_becoming_a_notice(self):
        sets={'A.AS':self.animation_set('A.AS',refs=['B']),
              'B.AS':self.animation_set('B.AS',refs=['C']),
              'C.AS':self.animation_set('C.AS')}
        with patch('identity_fixture.animation_catalog.MAX_ANIMATION_SETS',2):
            with self.assertRaisesRegex(FormatError,'graph exceeds limit'):
                self.read_catalog(sets,'A')

    def test_bank_member_path_is_not_replaced_by_another_basename(self):
        sets={'Main.AS':self.animation_set('Main.AS',files=['A/Idle'])}
        self.file('Main_AN4_NXG.PAK',bank(['A/Idle_DEF_NXG.AN4','B/Idle_DEF_NXG.AN4']))
        report=self.read_catalog(sets,'Main.AS')
        self.assertEqual(report['entries'][0]['member'],'A/Idle_DEF_NXG.AN4')
        self.assertEqual(report['entries'][0]['status'],'Bank member')

    def test_ambiguous_bank_member_is_not_rescued_by_unrelated_loose_clip(self):
        sets={'Main.AS':self.animation_set('Main.AS',files=['Idle'])}
        self.file('Main_AN4_NXG.PAK',bank(['A/Idle_DEF_NXG.AN4','B/Idle_DEF_NXG.AN4']))
        self.file('Unrelated/Idle_DEF_NXG.AN4')
        report=self.read_catalog(sets,'Main')
        self.assertEqual(report['entries'][0]['source'],'')
        self.assertIn('Ambiguous',report['entries'][0]['status'])

    def test_missing_qualified_clip_does_not_fall_back_to_unrelated_file(self):
        sets={'Main.AS':self.animation_set('Main.AS',files=['Missing/Idle'])}
        self.file('Other/Idle_DEF_NXG.AN4')
        report=self.read_catalog(sets,'Main')
        self.assertEqual(report['entries'][0]['source'],'')
        self.assertEqual(report['entries'][0]['status'],'Missing source')

    def test_existing_tfa_reference_inspection_does_not_enable_character_import(self):
        sets={'Main.AS':self.animation_set('Main.AS',files=['Idle'])}
        self.file('Main_AN4_DX11.PAK',bank(['Idle_DEF_DX11.AN4']))
        report=self.read_catalog(sets,'Main',game='TFA')
        self.assertEqual(report['profile_identity']['support_scope'],'reference_inspection_only')
        self.assertEqual(report['entries'][0]['member'],'Idle_DEF_DX11.AN4')
        with self.assertRaises(FormatError):character_profile('TFA')

    def test_lotr_does_not_guess_dx11_animation_names(self):
        sets={'Main.AS':self.animation_set('Main.AS',files=['Declared.AN4','GuessMe'])}
        self.file('Declared.AN4')
        self.file('GuessMe_DEF_DX11.AN4')
        report=self.read_catalog(sets,'Main',game='LOTR')
        self.assertEqual(report['entries'][0]['source_logical_path'],'Declared.AN4')
        self.assertEqual(report['entries'][1]['source'],'')
        self.assertIn('unverified',report['entries'][1]['status'])


def skeleton(name):
    rig={'version':16,'byte_order':'big','joints':[{'index':0,'name':name,'parent':None,
         'local_bind_row_major':list(I4),'inverse_world_bind_row_major':list(I4)}]}
    rig['identity']=skeleton_identity(rig)
    return rig


def attachment(identifier, resource, *, parent=None, root=None):
    rig=skeleton(root or resource)
    identity=model_resource_identity(Path(resource+'.GHG'),rig,reference=resource,game='LB3')
    return {'id':identifier,'parent_id':parent,'skeleton':rig,'identity':identity}


def actor(index,name,parent=None,clip='Idle',nodes=1,frames=3):
    return {'index':index,'offset':72+index*72,'name':name,'parent':parent,
            'records':[{'name':clip,'animation':types.SimpleNamespace(nodes=nodes,frames=frames)}]}


class AttachmentOwnershipTests(unittest.TestCase):
    def test_consumed_locator_has_a_valid_native_joint(self):
        rig=skeleton('Body')
        point={'name':'Hand','joint':0,'matrix':list(I4)}
        rig['points_of_interest']=[point]
        rig['post_poi_bytes']=[0]
        self.assertIs(attachment_locator(rig,0),point)

    def test_invalid_consumed_locator_and_joint_do_not_use_python_negative_indices(self):
        rig=skeleton('Body')
        rig['points_of_interest']=[{'name':'Hand','joint':0,'matrix':list(I4)}]
        rig['post_poi_bytes']=[0]
        for logical in (-1,1):
            with self.subTest(logical=logical):
                with self.assertRaises(FormatError):attachment_locator(rig,logical)
        for remap in (-1,255):
            rig['post_poi_bytes']=[remap]
            with self.subTest(remap=remap):
                with self.assertRaises(FormatError):attachment_locator(rig,0)
        rig['post_poi_bytes']=[0]
        for joint in (-1,255):
            rig['points_of_interest'][0]['joint']=joint
            with self.subTest(joint=joint):
                with self.assertRaises(FormatError):attachment_locator(rig,0)
                self.assertEqual(rig['points_of_interest'][0]['joint'],joint)

    def test_resource_identity_disambiguates_equal_counts_and_clip_labels(self):
        actors=[actor(0,'Body'),actor(1,'Cape',0),actor(2,'Face',0)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle',frames=3)
        self.assertEqual(matched['face']['actor']['index'],2)
        self.assertEqual(matched['face']['evidence']['kind'],'declared_resource')
        self.assertEqual(issues,[])

    def test_labels_and_counts_without_identity_are_insufficient(self):
        actors=[actor(0,'Body'),actor(1,'Other',0)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle')
        self.assertFalse(matched)
        self.assertIn('resource or native skeleton identity',issues[0]['issue'])

    def test_same_named_actor_under_another_root_is_excluded(self):
        actors=[actor(0,'Body'),actor(1,'OtherBody'),actor(2,'Face',1)]
        matched,_=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle')
        self.assertFalse(matched)

    def test_clip_label_cannot_choose_between_ambiguous_resource_actors(self):
        actors=[actor(0,'Body'),actor(1,'Face',0),actor(2,'Face',0,clip='Run')]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle')
        self.assertFalse(matched)
        self.assertEqual(len(issues[0]['actor_candidates']),2)

    def test_competing_attachment_instances_reject_both_claims(self):
        actors=[actor(0,'Body'),actor(1,'Face',0)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('first','Face'),attachment('second','Face')],'Idle')
        self.assertFalse(matched)
        self.assertEqual(len(issues),2)
        self.assertTrue(all('multiple attachment instances' in issue['issue'] for issue in issues))

    def test_nested_attachments_follow_matched_native_parent(self):
        actors=[actor(0,'Body'),actor(1,'Cape',0),actor(2,'Fastener',1),actor(3,'Fastener',0)]
        instances=[attachment('fastener','Fastener',parent='cape'),attachment('cape','Cape')]
        matched,issues=attachment_tracks(actors,actors[0],instances,'Idle')
        self.assertEqual(matched['fastener']['actor']['index'],2)
        self.assertEqual(issues,[])

    def test_missing_parent_identity_does_not_promote_nested_child(self):
        actors=[actor(0,'Body'),actor(1,'Fastener',0)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('child','Fastener',parent='missing')],'Idle')
        self.assertFalse(matched)
        self.assertIn('Parent attachment',issues[0]['issue'])

    def test_stale_native_binding_identity_is_rejected(self):
        actors=[actor(0,'Body'),actor(1,'Face',0)]
        instance=attachment('face','Face')
        instance['skeleton']['joints'][0]['local_bind_row_major'][12]=3
        matched,issues=attachment_tracks(actors,actors[0],[instance],'Idle')
        self.assertFalse(matched)
        self.assertIn('differs',issues[0]['issue'])

    def test_missing_retained_identity_requests_reimport(self):
        actors=[actor(0,'Body'),actor(1,'Face',0)]
        instance=attachment('face','Face')
        instance['identity']=None
        matched,issues=attachment_tracks(actors,actors[0],[instance],'Idle')
        self.assertFalse(matched)
        self.assertIn('reimport',issues[0]['issue'])

    def test_native_root_name_evidence_is_explicit(self):
        actors=[actor(0,'Body'),actor(1,'FaceRig',0)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','SharedFaceResource',root='FaceRig')],'Idle')
        self.assertEqual(matched['face']['evidence']['kind'],'native_skeleton_root')
        self.assertEqual(issues,[])

    def test_duration_is_checked_after_identity(self):
        actors=[actor(0,'Body'),actor(1,'Face',0,frames=7)]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle',frames=3)
        self.assertFalse(matched)
        self.assertIn('duration',issues[0]['issue'])

    def test_static_or_missing_animation_records_are_diagnosed(self):
        actors=[actor(0,'Body'),actor(1,'Face',0)]
        actors[1]['records']=[{'name':'Idle'},{'name':'Idle','animation':None}]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('face','Face')],'Idle')
        self.assertFalse(matched)
        self.assertIn('no unique clip',issues[0]['issue'])

    def test_root_actor_must_belong_to_the_source_tree(self):
        actors=[actor(0,'Body'),actor(1,'Face',0)]
        with self.assertRaisesRegex(FormatError,'absent from the animation tree'):
            attachment_tracks(actors,actor(99,'Foreign'),[attachment('face','Face')],'Idle')

    def test_cyclic_attachment_ownership_is_reported(self):
        actors=[actor(0,'Body')]
        matched,issues=attachment_tracks(actors,actors[0],[attachment('a','A',parent='b'),attachment('b','B',parent='a')],'Idle')
        self.assertFalse(matched)
        self.assertEqual(len(issues),2)
        self.assertTrue(all('Cyclic' in issue['issue'] for issue in issues))


if __name__=='__main__':
    unittest.main()
