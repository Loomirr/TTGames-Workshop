"""Original-file optional-attachment rollback and dependency export regression.

User-supplied game files stay outside Git. Run against an extracted addon ZIP.
"""
import argparse,json,sys
from pathlib import Path
from unittest.mock import patch
import bpy

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--addon-directory',required=True,type=Path)
p.add_argument('--game-root',required=True,type=Path)
p.add_argument('--cache-root',required=True,type=Path)
p.add_argument('--output-root',required=True,type=Path)
p.add_argument('--character',default='WOLVERINE')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
args.output_root=args.output_root.resolve()
if any(args.output_root.is_relative_to(root.resolve()) for root in (args.game_root,args.cache_root)):
    p.error('Choose an output root outside the game and source/cache tree')
args.output_root.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(args.addon_directory))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character import importer
from io_scene_tt_character.exporter import export_sources
from io_scene_tt_character._core.asset_index import open_assets
from io_scene_tt_character._core.cu3 import FormatError
assets=open_assets(args.game_root,'LMSH1',args.cache_root)
cd=assets.find(args.character,extension='.CD')
original_attachments=importer.active_attachments
original_resolve=importer.ResourceResolver.resolve
original_materials=importer.CostumeMaterials
current={}
failed='__P1_FAILED_ATTACHMENT__'
def material_factory(*a,**kw):
    factory=original_materials(*a,**kw);current['factory']=factory;return factory
def attachments(definition,**kw):
    values=list(original_attachments(definition,**kw))
    if Path(definition['source'])!=cd:return values
    assert values,'Use a specimen with optional attachments'
    # Exercise success -> failure -> success as well as a final failure.
    broken=dict(values[0],**{'Resource File':failed})
    return values+[broken] if current['final_failure'] else [values[0],broken]+values[1:]+[values[0]]
def resolve(self,reference):
    if reference!=failed:return original_resolve(self,reference)
    factory=current['factory']
    shared=next(k for k in factory.images if isinstance(k,Path))
    image=factory.image(shared)
    assert image in bpy.data.images.values()
    unused=args.output_root/('failed-'+str(current['final_failure'])+'.TEX')
    unused.write_bytes(shared.read_bytes())
    factory.image(unused)
    current['failed_source']=unused.resolve()
    current['failed_images']={factory.images[unused]}
    raise FormatError('Injected optional attachment failure after texture creation')
for final_failure in (True,False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    current['final_failure']=final_failure
    with patch.object(importer,'CostumeMaterials',material_factory),patch.object(importer,'active_attachments',attachments),patch.object(importer.ResourceResolver,'resolve',resolve):
        rig,report=importer.import_character(bpy.context,cd,assets.root,'LMSH1',assets=assets)
    assert any('Injected optional attachment' in str(x) for x in report['issues'])
    sources=json.loads(rig['tt_native_texture_sources'])
    assert sources,'Surviving body texture provenance was cleared by attachment rollback'
    assert str(current['failed_source']) not in sources
    assert not current['failed_images'].intersection(set(bpy.data.images))
    assert current['factory'].images,'Surviving image cache was discarded'
    if final_failure:
        candidates=[json.loads(item.payload) for item in rig.tt_animation_assets
                    if item.available and 'idle' in item.name.casefold()]
        assert candidates,'Use a specimen with a declared idle animation'
        selected=next((entry for entry in candidates if importer.import_catalog_entry(bpy.context,rig,entry)['imported']),None)
        assert selected,'No supported idle clip in this specimen'
    result=export_sources(rig,args.output_root/('export-'+str(final_failure)))
    names={Path(f['path']).name.casefold() for f in result['files']}
    assert all(Path(s).name.casefold() in names for s in sources)
    assert all(v['changed_bytes']==0 for v in result['vertex_patches'].values())
    print('DEPENDENCY_ROLLBACK_PASS',final_failure,len(sources),flush=True)
    if final_failure:
        # Work on our exported fixture, never the installation or old cache.
        fixture=args.output_root/('export-'+str(final_failure))
        fixture_assets=open_assets(fixture,'LMSH1')
        copied_cd=fixture_assets.find(args.character,extension='.CD')
        fresh,_=importer.import_character(bpy.context,copied_cd,fixture,'LMSH1',assets=fixture_assets)
        from io_scene_tt_character._core.animation_bank import AnimationBank
        bank_source=fixture/Path(json.loads(rig['tt_native_source_provenance'])['records'][str(Path(selected['source']).resolve())]['logical_path'])
        assert selected['member'],'Use a bank-backed original idle sample for this check'
        loose=fixture/'P1_IDLE.AN4';loose.write_bytes(AnimationBank(bank_source).read(selected['member']))
        assert importer.import_animations(bpy.context,fresh,[loose])['imported']
        reexport=export_sources(fresh,args.output_root/'reimport-export')
        for f in reexport['files']:
            assert (fixture/f['path']).read_bytes()==(args.output_root/'reimport-export'/f['path']).read_bytes()
        records=json.loads(fresh['tt_native_source_provenance'])['records']
        for extension in ('.cd','.tex','.as','.pak','.an4'):
            source=next(Path(k) for k in records if Path(k).suffix.casefold()==extension)
            original=source.read_bytes();source.write_bytes(original+b'changed companion')
            destination=args.output_root/('rejected-'+extension[1:])
            try:
                try:export_sources(fresh,destination)
                except FormatError as error:assert 'changed since import' in str(error),error
                else:raise AssertionError('Changed companion was accepted: '+str(source))
                assert not destination.exists(),'Changed companion left output files'
            finally:source.write_bytes(original)
            print('COMPANION_GUARD_PASS',extension,flush=True)
print('DEPENDENCY_ROLLBACK_CHECK_PASSED')
