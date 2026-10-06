"""Shared character resource resolution and read-only dependency preflight.

This discovers declared companions in an extracted asset tree. It does not
extract archives or claim that a resolved file can be decoded/rendered.
"""
import re
from pathlib import PurePosixPath
from .cu3 import FormatError
from .definitions import character_definition
from .profiles import CHARACTER_PROFILES, character_profile, profile_identity, active_renderer_reference, require_active_renderer
from .resource_identity import logical_reference, logical_path, reference_cycles

PROFILES = {game:(info['cutscene_version'],info['model_suffix']) for game,info in CHARACTER_PROFILES.items()}


def actor_resource(name):
    return re.sub(r'^instance[^_]*_', '', name, flags=re.I)


def active_attachments(definition, *, layer_mode='authored', renderer_suffix=None):
    if definition is None:return []
    character=definition['character']
    if layer_mode not in ('authored', 'default', 'cutscene'):
        raise FormatError('Unknown attachment layer selection mode')
    mask=(character.get('Default Layers',0) if layer_mode=='default' else character.get('Cutscene Layers',0)
          if layer_mode=='cutscene' else character.get('Default Layers',0) if character.get('Use Default Layers',-1)&2
          else character.get('Cutscene Layers',0))
    result=[]
    for item in definition['objects']:
        if item['class']!='Character Attachment':continue
        fields=item['fields'];layer=fields.get('Layer')
        if not isinstance(layer,int) or not 0<=layer<64:
            raise FormatError('Attachment layer is missing or outside the native 64-bit mask')
        # Empty customization slots are declarations, not asset references.
        if mask & (1 << layer) and fields.get('Resource File'):
            if renderer_suffix and not active_renderer_reference(fields['Resource File'], renderer_suffix):continue
            result.append(fields)
    return result


class MissingResource(FormatError):
    def __init__(self, reference, candidates):
        self.reference, self.candidates=reference,candidates
        super().__init__(f'Missing resource {reference}; supply one of: '+', '.join(candidates))


class ResourceResolver:
    def __init__(self, assets, profile, replacements=None):
        if profile not in PROFILES:raise FormatError('Unsupported game profile')
        if getattr(assets,'profile',profile)!=profile:
            raise FormatError('Asset provider belongs to a different game profile')
        self.assets=assets
        self.profile=profile
        self.profile_info=character_profile(profile)
        self.identity=profile_identity(profile)
        self.version,self.suffix=PROFILES[profile]
        self.cache={}
        from .scene_configuration import compile_character_replacements
        if replacements is not None and not isinstance(replacements, dict):
            raise FormatError('Character replacements must be a resource mapping')
        self.replacements=compile_character_replacements({'character_replacements':[
            {'original':key,'replacement':value} for key,value in (replacements or {}).items()]})

    def actor_reference(self, actor_name):
        """Resolve one root actor's resource without renaming its source node."""
        reference=actor_resource(actor_name)
        return self.replacements.get(reference.casefold(),reference)

    def validate_cutscene(self, cut):
        if self.version is None:
            raise FormatError('This profile supports characters; cutscene assembly is not verified')
        if cut.version!=self.version:
            raise FormatError('Cutscene version does not match the selected game profile')

    def resolve(self, reference):
        reference=logical_reference(reference)
        require_active_renderer(reference,self.suffix)
        key=reference.casefold()
        if key in self.cache:return dict(self.cache[key],reference=reference)
        definition_path=self.assets.find(reference,extension='.CD',required=False)
        definition=character_definition(definition_path) if definition_path else None
        model_reference=reference
        if definition:
            fields=definition['character']
            model_reference=fields.get('Override Model File') or fields['Skeleton Name']
        model=self.resolve_model(model_reference,required=False)
        if model is None:
            relative=PurePosixPath(str(model_reference).replace('\\','/'))
            stem=relative.stem
            if not stem.casefold().endswith(self.suffix.casefold()):stem+=self.suffix
            candidates=[relative.with_name(stem+ext).as_posix() for ext in ('.GHG','.GSC')]
            if not definition_path:
                candidates.insert(0,PurePosixPath(str(reference).replace('\\','/')).stem+'.CD (which may name a different model)')
            raise MissingResource(reference,candidates)
        result={'reference':reference,'model':model,'definition_path':definition_path,'definition':definition,
                'logical_model':logical_path(self.assets,model),
                'logical_definition':logical_path(self.assets,definition_path) if definition_path else None,
                'profile_identity':self.identity}
        self.cache[key]=result
        return result

    def resolve_model(self, reference, *, required=True):
        reference=logical_reference(reference)
        require_active_renderer(reference,self.suffix)
        extension=PurePosixPath(reference).suffix.upper()
        extensions=(extension,) if extension in ('.GHG','.GSC') else ('.GHG','.GSC')
        for extension in extensions:
            model=self.assets.find(reference,self.suffix,extension,required=False)
            if model is not None:return model
        if required:
            relative=PurePosixPath(reference)
            stem=relative.stem
            if not stem.casefold().endswith(self.suffix.casefold()):stem+=self.suffix
            raise MissingResource(reference,[relative.with_name(stem+extension).as_posix() for extension in extensions])
        return None


def dependency_report(cut, resolver):
    resolver.validate_cutscene(cut)
    queue=[(resolver.actor_reference(a['name']),a['name']) for a in cut.actors if a['parent'] is None and a['records']]
    resources,rows,edges={},[],[]
    while queue:
        reference,owner=queue.pop(0)
        key=str(reference).replace('\\','/').casefold()
        if key in resources:
            if owner not in resources[key]['requested_by']:resources[key]['requested_by'].append(owner)
            continue
        if len(resources)>=10000:raise FormatError('Dependency graph exceeds the supported resource limit')
        row={'reference':reference,'requested_by':[owner]};resources[key]=row;rows.append(row)
        try:
            resolved=resolver.resolve(reference)
            model,definition=resolved['model'],resolved['definition']
            row.update(status='resolved',model=str(model),definition=str(resolved['definition_path']) if definition else None,textures=[],
                       logical_model=resolved['logical_model'],logical_definition=resolved['logical_definition'],inactive_renderer_references=[])
            model_logical=resolved['logical_model']
            store=None
            try:
                store=resolver.assets.find_exact(PurePosixPath(model_logical).with_suffix('.NXG_TEXTURES').as_posix(),required=False) if model_logical else None
                if store is None:store=resolver.assets.find(model.stem+'.NXG_TEXTURES',required=False)
            except (ValueError,OSError) as error:
                row.setdefault('issues',[]).append('Optional texture-store lookup: '+str(error))
            row['texture_store']=str(store) if store else None
            row['texture_store_note']='Optional here; native material bindings determine whether this store is needed.'
            if definition:
                row['definition_partial']=any(not obj['complete'] for obj in definition['objects'])
                for name in sorted({obj['fields']['Texture File'] for obj in definition['objects'] if obj['fields'].get('Texture File')}):
                    if not active_renderer_reference(name,resolver.suffix):
                        row['inactive_renderer_references'].append({'role':'texture','reference':name})
                        continue
                    texture={'reference':name}
                    try:
                        path=resolver.assets.find(name,resolver.suffix,'.TEX',required=False)
                        texture.update(status='resolved' if path else 'missing',path=str(path) if path else None,
                                       logical_path=logical_path(resolver.assets,path) if path else None)
                    except (ValueError,OSError) as error:texture.update(status='unresolved',issue=str(error))
                    row['textures'].append(texture)
                for attachment in active_attachments(definition):
                    child=attachment.get('Resource File')
                    if child and not active_renderer_reference(child,resolver.suffix):
                        row['inactive_renderer_references'].append({'role':'attachment','reference':child})
                        continue
                    if child:
                        edges.append({'owner':reference,'resource':child,'role':'attachment','layer':attachment['Layer']})
                        queue.append((child,reference))
                    else:row.setdefault('issues',[]).append('An active attachment resource field is not decoded')
        except MissingResource as error:
            row.update(status='missing',candidates=error.candidates,issue=str(error))
        except (ValueError,OSError,KeyError) as error:
            row.update(status='unresolved',issue=str(error))
    identities={key:str(row.get('logical_definition') or row.get('logical_model') or key).casefold()
                for key,row in resources.items()}
    cycles=reference_cycles([(edge['owner'],edge['resource']) for edge in edges],identities)
    return {'schema':'tt.cutscene-dependencies.v1','source':str(cut.path),'resources':rows,
            'profile_identity':resolver.identity,'attachment_edges':edges,'cycles':cycles,
            'resolved_resources':sum(r['status']=='resolved' for r in rows),
            'missing_resources':sum(r['status']=='missing' for r in rows),
            'unresolved_resources':sum(r['status']=='unresolved' for r in rows),
            'missing_textures':sum(t['status']!='resolved' for r in rows for t in r.get('textures',[])),
            'scope':'Active renderer root actors, active character attachments and decoded costume texture declarations. Cycles are reported, not expanded. Nested undecoded CD fields, environments, rigid objects, audio and VFX remain outside this closure; file presence is not decoder or fidelity validation.'}
