"""Consumed native dependency revisions, independent of Blender image caching."""
import copy
import hashlib
import json
from pathlib import Path
from .cu3 import FormatError


class SourceProvenance:
    def __init__(self, assets=None, records=None):
        self.assets=assets
        self.records=copy.deepcopy(records or {})

    def snapshot(self):
        return copy.deepcopy(self.records)

    def restore(self, records):
        self.records=copy.deepcopy(records)

    def record(self, path, role, *, data=None, digest=None, export=True, member=None):
        path=Path(path).resolve();key=str(path)
        digest=digest or hashlib.sha256(path.read_bytes() if data is None else data).hexdigest()
        old=self.records.get(key)
        if old and old['sha256']!=digest:
            raise FormatError('Native dependency changed while being consumed: '+key)
        if old:
            old['roles']=sorted(set(old['roles'])|{role})
            old['export']=old['export'] or export
        else:
            root=Path(self.assets.root).resolve() if self.assets else None
            logical=path.relative_to(root).as_posix() if root and path.is_relative_to(root) else path.name
            old=dict(path=key,logical_path=logical,roles=[role],sha256=digest,
                     consumed_revision=digest,export=export)
            if root:old['source_root']=str(root)
            if self.assets:
                old['profile']=getattr(self.assets,'profile','')
                # Archive providers retain full member paths and declared spans.
                matches=[(a,e) for item in self.assets.files.get(path.name.casefold(),[])
                         if isinstance(item,tuple) for a,e in [item]
                         if (root/e['path']).resolve()==path]
                if matches:
                    old['archive_members']=[dict(archive=str(a.resolve()),path=e['path'],
                        offset=e['offset'],packed_size=e['packed_size'],decoded_size=e['size'],
                        archive_size=a.stat().st_size,archive_mtime_ns=a.stat().st_mtime_ns) for a,e in matches]
            self.records[key]=old
        if member and member not in old.setdefault('animation_members',[]):
            old['animation_members'].append(copy.deepcopy(member))
        return old

    def dumps(self):
        return json.dumps(dict(schema='tt.source-provenance.v1',records=self.records),sort_keys=True)

    @classmethod
    def loads(cls, text, assets=None):
        if not text:raise FormatError('Missing consumed dependency revisions; reimport with the current addon before native export')
        value=json.loads(text)
        if value.get('schema')!='tt.source-provenance.v1' or not isinstance(value.get('records'),dict):
            raise FormatError('Unsupported native source provenance')
        return cls(assets,value['records'])

    def verify(self):
        """Read every recorded companion before any destination is created."""
        verified={}
        for key,record in self.records.items():
            path=Path(key)
            try:data=path.read_bytes()
            except OSError as error:
                raise FormatError('Native dependency missing/unreadable since import: '+key) from error
            if hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise FormatError('Native dependency changed since import: '+', '.join(record['roles'])+' / '+key)
            if record['export']:verified[path.resolve()]=data
        return verified
