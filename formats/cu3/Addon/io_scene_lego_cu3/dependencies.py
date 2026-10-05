"""Shared character resource resolution and read-only dependency preflight.

This discovers declared companions in an extracted asset tree. It does not
extract archives or claim that a resolved file can be decoded/rendered.
"""
import re
from pathlib import PurePosixPath
from .cu3 import FormatError
from .definitions import character_definition

PROFILES = {'LB3':(19,'_DX11'), 'LMSH1':(18,'_NXG'), 'HOBBIT':(None,'_NXG')}


def actor_resource(name):
    return re.sub(r'^instance[^_]*_', '', name, flags=re.I)


def active_attachments(definition, *, layer_mode='authored'):
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
        if mask & (1 << layer) and fields.get('Resource File'):result.append(fields)
    return result


class MissingResource(FormatError):
    def __init__(self, reference, candidates):
        self.reference, self.candidates=reference,candidates
        super().__init__(f'Missing resource {reference}; supply one of: '+', '.join(candidates))


class ResourceResolver:
    def __init__(self, assets, profile, replacements=None):
        if profile not in PROFILES:raise FormatError('Unsupported game profile')
        self.assets=assets
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
        key=str(reference).replace('\\','/').casefold()
        if key in self.cache:return self.cache[key]
        definition_path=self.assets.find(reference,extension='.CD',required=False)
        definition=character_definition(definition_path) if definition_path else None
        model_reference=reference
        if definition:
            fields=definition['character']
            model_reference=fields.get('Override Model File') or fields['Skeleton Name']
        model=(self.assets.find(model_reference,self.suffix,'.GHG',required=False) or
               self.assets.find(model_reference,self.suffix,'.GSC',required=False))
        if model is None:
            stem=PurePosixPath(str(model_reference).replace('\\','/')).stem
            if not stem.casefold().endswith(self.suffix.casefold()):stem+=self.suffix
            candidates=[stem+'.GHG',stem+'.GSC']
            if not definition_path:
                candidates.insert(0,PurePosixPath(str(reference).replace('\\','/')).stem+'.CD (which may name a different model)')
            raise MissingResource(reference,candidates)
        result={'reference':reference,'model':model,'definition_path':definition_path,'definition':definition}
        self.cache[key]=result
        return result


def dependency_report(cut, resolver):
    resolver.validate_cutscene(cut)
    queue=[(resolver.actor_reference(a['name']),a['name']) for a in cut.actors if a['parent'] is None and a['records']]
    resources,rows={},[]
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
            row.update(status='resolved',model=str(model),definition=str(resolved['definition_path']) if definition else None,textures=[])
            store=resolver.assets.find(model.stem+'.NXG_TEXTURES',required=False)
            row['texture_store']=str(store) if store else None
            row['texture_store_note']='Optional here; native material bindings determine whether this store is needed.'
            if definition:
                row['definition_partial']=any(not obj['complete'] for obj in definition['objects'])
                for name in sorted({obj['fields']['Texture File'] for obj in definition['objects'] if obj['fields'].get('Texture File')}):
                    texture={'reference':name}
                    try:
                        path=resolver.assets.find(name,resolver.suffix,'.TEX',required=False)
                        texture.update(status='resolved' if path else 'missing',path=str(path) if path else None)
                    except (ValueError,OSError) as error:texture.update(status='unresolved',issue=str(error))
                    row['textures'].append(texture)
                for attachment in active_attachments(definition):
                    child=attachment.get('Resource File')
                    if child:queue.append((child,reference))
                    else:row.setdefault('issues',[]).append('An active attachment resource field is not decoded')
        except MissingResource as error:
            row.update(status='missing',candidates=error.candidates,issue=str(error))
        except (ValueError,OSError,KeyError) as error:
            row.update(status='unresolved',issue=str(error))
    return {'schema':'tt.cutscene-dependencies.v1','source':str(cut.path),'resources':rows,
            'resolved_resources':sum(r['status']=='resolved' for r in rows),
            'missing_resources':sum(r['status']=='missing' for r in rows),
            'unresolved_resources':sum(r['status']=='unresolved' for r in rows),
            'missing_textures':sum(t['status']!='resolved' for r in rows for t in r.get('textures',[])),
            'scope':'Root actors, active character attachments and declared costume textures. Does not cover environments, rigid objects, audio or VFX; file presence is not decoder or fidelity validation.'}
