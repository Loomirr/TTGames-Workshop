"""Canonical shared-source edit proposals; no Blender dependency."""
import os
from pathlib import Path
from ._core.cu3 import FormatError


def canonical_source(path):
    """Resolve relative/symlink aliases and the host's case normalization."""
    return Path(os.path.normcase(str(Path(path).expanduser().resolve())))


def group_source_instances(instances):
    """Group (path, instance) pairs before any instance produces a payload."""
    groups = {}
    for path, instance in instances:
        groups.setdefault(canonical_source(path), []).append(instance)
    return groups


class SourceProposals:
    """Every instance of a source must propose the same complete native bytes.

    Comparing only changed ranges would miss an edited/unchanged conflict, or
    silently combine edits that no instance actually proposed. Compare bytes,
    not just digests, including instances that propose the original file.
    """
    def __init__(self, source):
        self.source = canonical_source(source)
        self.payload = None
        self.instances = []

    def add(self, instance, payload):
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise FormatError('Native source proposal must contain bytes')
        payload = bytes(payload)
        first = self.payload is None
        if not first and payload != self.payload:
            raise FormatError(
                'Conflicting native source instances for ' + str(self.source) + ': '
                + ', '.join(self.instances) + ' / ' + str(instance)
                + '. Every instance must agree, including unchanged instances.')
        if first:
            self.payload = payload
        self.instances.append(str(instance))
        return first
