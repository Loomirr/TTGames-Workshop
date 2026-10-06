"""Resolve attachment tracks from source hierarchy and retained native identity.

AN4 does not store bind matrices. Names identify a declared resource or its
native skeleton root only within an already matched parent. Clip labels,
joint counts and durations then validate a candidate; they never identify it.
"""
from .cu3 import FormatError
from .resource_identity import actor_identity_evidence
from .skeleton import skeleton_identity


def attachment_tracks(actors, root_actor, attachments, clip_name, frames=None):
    """Resolve a whole attachment tree, rejecting competing sibling claims.

    ``attachments`` carry id, parent_id (None for root children), skeleton and
    identity. The caller supplies these from retained import data, never from
    an animation label. All matches are chosen before any pose is created.
    """
    ids = [attachment['id'] for attachment in attachments]
    if len(ids) != len(set(ids)):
        raise FormatError('Duplicate attachment instance identity')
    known = set(ids)
    pending = list(attachments)
    matched, issues, completed = {}, [], set()
    actor_ids = [actor['index'] for actor in actors]
    if len(actor_ids) != len(set(actor_ids)):
        raise FormatError('Duplicate animation actor identity')
    if root_actor is None or root_actor.get('index') not in set(actor_ids):
        raise FormatError('Selected root actor is absent from the animation tree')

    def fail(attachment, message, candidates=()):
        issues.append({'attachment': attachment['id'], 'issue': message,
                       'actor_candidates': [{'index': actor['index'], 'name': actor['name'],
                                             'offset': actor.get('offset')} for actor in candidates]})

    while pending:
        level = [item for item in pending if item.get('parent_id') is None or
                 item.get('parent_id') in completed or item.get('parent_id') not in known]
        if not level:
            for item in pending:
                fail(item, 'Cyclic attachment ownership; no track applied')
            break
        proposals = {}
        for item in level:
            pending.remove(item)
            parent_id = item.get('parent_id')
            parent_actor = root_actor if parent_id is None else matched.get(parent_id, {}).get('actor')
            if parent_actor is None:
                fail(item, 'Parent attachment has no verified animation ownership')
                continue
            identity, skeleton = item.get('identity'), item.get('skeleton')
            if not identity or not skeleton or not identity.get('skeleton_identity'):
                fail(item, 'Missing retained native resource/skeleton identity; reimport the character')
                continue
            if identity['skeleton_identity'] != skeleton_identity(skeleton):
                fail(item, 'Attachment skeleton differs from its retained native identity')
                continue
            named = []
            for actor in actors:
                if actor.get('parent') != parent_actor['index']:
                    continue
                evidence = actor_identity_evidence(actor, identity)
                if evidence:
                    named.append((actor, evidence))
            if len(named) != 1:
                fail(item, 'No unique attachment actor with declared resource or native skeleton identity under its parent',
                     [actor for actor, _ in named])
                continue
            actor, evidence = named[0]
            records = []
            for index, record in enumerate(actor.get('records', [])):
                animation = record.get('animation')
                nodes, duration = getattr(animation,'nodes',None), getattr(animation,'frames',None)
                if (animation is not None and isinstance(duration,int) and duration > 0 and
                        (clip_name is None or record.get('name','').casefold() == clip_name.casefold()) and
                        nodes == len(skeleton['joints']) and (frames is None or duration == frames)):
                    records.append((index,record))
            if len(records) != 1:
                fail(item, 'Named attachment actor has no unique clip with matching joint count and duration', [actor])
                continue
            index, record = records[0]
            proposals[item['id']] = {'actor': actor, 'record_index': index, 'record': record,
                                     'evidence': dict(evidence, parent_actor_index=parent_actor['index'])}
        claims = {}
        for instance, proposal in proposals.items():
            claims.setdefault(proposal['actor']['index'], []).append(instance)
        for item in level:
            completed.add(item['id'])
            proposal = proposals.get(item['id'])
            if proposal is None:
                continue
            competing = claims[proposal['actor']['index']]
            if len(competing) != 1:
                fail(item, 'Animation actor is claimed by multiple attachment instances: ' + ', '.join(map(str, competing)),
                     [proposal['actor']])
            else:
                matched[item['id']] = proposal
    return matched, issues
