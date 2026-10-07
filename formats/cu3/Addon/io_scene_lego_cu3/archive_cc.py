"""Read observed Avengers/TFA/DCSV CC40TAD archive indexes without runtimes.

This is an inventory reader, not an archive writer. Entries retain compression
flags; callers must use a compatible decoder before treating bytes as a file.
Unknown versions, unresolved names and out-of-bounds tables are rejected.
"""
from pathlib import Path
import hashlib
import os
import struct
from .archive_paths import safe_path, validate_paths

MAX_INDEX_BYTES = 256 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 64
MAX_DIAGNOSTIC_TAGS = 16
MAX_DIAGNOSTIC_ERROR_CHARS = 1024
MAX_SUFFIX_PREFIX_BYTES = 4096


class CCIndexError(ValueError):
    """A parser refusal with bounded, non-extractable inspection metadata."""
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def path_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def _safe_name(name):
    return safe_path(name)


def _parse_tables(data, archive_limit=None, *, expected_layout=None, trace):
    """Validate the currently understood tables, not an unknown suffix."""
    trace.update(phase='header', table_spans=[])
    if len(data) > MAX_INDEX_BYTES:
        raise ValueError('CC8 index exceeds size limit')
    if archive_limit is not None and (not isinstance(archive_limit, int) or archive_limit < 8):
        raise ValueError('Invalid CC8 archive data region')
    def read(fmt, at):
        trace['cursor'] = at
        size = struct.calcsize('>' + fmt)
        if at < 0 or at + size > len(data):
            raise ValueError('CC8 table exceeds index bounds')
        result = struct.unpack_from('>' + fmt, data, at)
        return result[0] if len(result) == 1 else result

    def string(at, end):
        if not 0 <= at < end <= len(data):
            raise ValueError('CC8 string exceeds its table')
        null = data.find(b'\0', at, end)
        if null < 0:
            raise ValueError('Unterminated CC8 name')
        return data[at:null].decode('ascii'), null + 1

    size, magic, kind, version, files, names, string_size = read('I8si4I', 0)
    trace['layout'] = dict(kind=kind, version=version, declared_index_bytes=size + 4,
                           file_count=files, name_count=names, string_bytes=string_size,
                           recognized=(kind, version) in ((-8, 1), (-8, 2), (-12, 2)))
    if size + 4 != len(data) or magic != b'.CC40TAD' or not trace['layout']['recognized']:
        raise ValueError('Unverified CC8 index version or declared size')
    trace['layout'].update(name_record_bytes=10 if version == 1 else 12,
                           path_hash_bits=64 if kind == -12 else 32)
    if expected_layout is not None and (kind, version) != expected_layout:
        raise ValueError(f'Unverified CC archive version {(kind, version)}; expected {expected_layout}')
    if not 0 < files <= 1000000 or not 0 < names <= 1000000:
        raise ValueError('Implausible CC8 counts')
    def span(name, start, end):
        trace['table_spans'].append(dict(name=name, offset=start, end=end, bytes=end-start))
    span('header', 0, 32)
    trace['phase'] = 'strings'
    strings_end = 32 + string_size
    read('I', strings_end)  # Serialized separator before the name records.
    span('strings', 32, strings_end)
    span('string_separator', strings_end, strings_end + 4)
    at = strings_end + 4
    names_at = at
    trace['phase'] = 'name_records'
    folders, paths = {}, []
    for i in range(names):
        if version == 1:
            name_offset, parent, sibling, file_marker = read('IHhH', at)
            at += 10
        else:
            name_offset, parent, unused, sibling, file_marker = read('IHHhH', at)
            at += 12
        if name_offset == 0xffffffff:
            continue
        if name_offset >= string_size:
            raise ValueError('CC8 name offset exceeds string table')
        name, _ = string(32 + name_offset, strings_end)
        if parent not in folders and parent not in (0, 65535):
            raise ValueError('CC8 name parent is unresolved')
        prefix = folders.get(parent, '')
        if not name and not prefix and not file_marker and i != names - 1 and parent in (0, 65535):
            folders[i] = ''
            continue
        full = _safe_name(prefix + '/' + name if prefix else name)
        # The terminal name omits its file marker in observed archives. It
        # still has to match a file hash or explicit named-override record.
        if file_marker or i == names - 1:
            paths.append(_safe_name(full))
        else:
            if parent not in folders and parent not in (0, 65535):
                raise ValueError('CC8 folder parent is unresolved')
            folders[i] = full
    validate_paths(paths)
    span('name_records', names_at, at)
    trace['phase'] = 'file_records'
    table_kind, count = read('iI', at)
    span('file_table_header', at, at + 8)
    at += 8
    if table_kind != kind or count != files:
        raise ValueError('CC8 file table disagrees with header')
    entries, files_at = [], at
    for i in range(files):
        if kind == -12:
            offset, packed, raw = read('QII', at)
            flags = (2 << 24) if raw & 0x80000000 else 0
            raw &= 0x7fffffff
        else:
            high, packed, raw, flags = read('4I', at)
            if flags & 0x00ffff00:
                raise ValueError('Unverified CC8 offset/flag bits')
            offset = (high << 8) + (flags & 255)
        at += 16
        if archive_limit is not None and (offset < 8 or offset + packed > archive_limit):
            raise ValueError('CC8 file bytes exceed archive data region')
        if bool(packed) != bool(raw) or (flags >> 24 == 0 and packed != raw):
            raise ValueError('Invalid CC8 packed/decoded sizes')
        entries.append(dict(offset=offset, packed_size=packed, size=raw, flags=flags >> 24))
    span('file_records', files_at, at)
    trace['phase'] = 'path_hashes'
    hash_size = 8 if kind == -12 else 4
    hashes = [read('Q' if kind == -12 else 'I', at + i * hash_size) for i in range(files)]
    span('path_hashes', at, at + files * hash_size)
    at += files * hash_size
    by_hash = {value: i for i, value in enumerate(hashes) if value}
    if len(by_hash) != sum(bool(value) for value in hashes):
        raise ValueError('Ambiguous CC8 path hash')
    trace['phase'] = 'named_overrides'
    override_count, override_size = (0, 0) if kind == -12 else read('2I', at)
    if kind != -12:
        span('named_override_header', at, at + 8)
    at += 0 if kind == -12 else 8
    override_end = at + override_size
    if override_count > files or override_end > len(data):
        raise ValueError('CC8 named override table exceeds bounds')
    overrides, overrides_at = {}, at
    for _ in range(override_count):
        name, cursor = string(at, override_end)
        # Names include their terminator and pad to an even byte count.
        cursor += (cursor - at) & 1
        if cursor + 2 > override_end:
            raise ValueError('Truncated CC8 named override')
        file_id = read('H', cursor)
        if file_id >= files or hashes[file_id] != 0:
            raise ValueError('CC8 named override must identify a zero-hash entry')
        name = _safe_name(name)
        key = name.casefold()
        if key in overrides or file_id in overrides.values():
            raise ValueError('Duplicate CC8 named override')
        overrides[key] = file_id
        at = cursor + 2
    if at != override_end:
        raise ValueError('CC8 named override size disagrees with records')
    if kind != -12:
        span('named_overrides', overrides_at, at)
    # A suffix refusal must not mask a corrupt path/hash relationship in the
    # already decoded prefix. Finish those checks before classifying the tail.
    trace['phase'] = 'path_mapping'
    mapped = {}
    for name in paths:
        if kind == -12:
            value = 0xcbf29ce484222325
            for byte in name.upper().replace('/', '\\').encode('ascii'):
                value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
        else:
            value = path_hash(name)
        file_id = overrides.get(name.casefold(), by_hash.get(value))
        if file_id is None:
            raise ValueError('CC8 path has no verified file reference: ' + name)
        if file_id in mapped:
            raise ValueError('Duplicate CC8 file reference')
        mapped[file_id] = dict(path=name, **entries[file_id])
    if len(mapped) != files:
        raise ValueError(f'CC8 mapped {len(mapped)} of {files} files')
    trace.update(phase='suffix', cursor=at, tables_end=at,
                 validated_file_count=len(mapped), named_override_count=len(overrides),
                 zero_path_hash_count=sum(value == 0 for value in hashes))
    return [mapped[i] for i in range(files)]


def _parse_rotv_suffix(data, rows, trace):
    """Read the two bounded opaque arrays observed in Avengers PC (-8, 1).

    Seventeen original indexes establish the framing and file-table order.
    They do not establish a checksum algorithm or codec. These records must
    never be interpreted as offsets, sizes, compression modes or path hashes.
    Other CC versions retain the unknown-suffix refusal.
    """
    start = trace['tables_end']
    if start == len(data):
        return
    layout = trace['layout']
    if (layout['kind'], layout['version']) != (-8, 1):
        return
    end = data.find(b'\0', start, min(len(data), start + MAX_SUFFIX_PREFIX_BYTES + 1))
    if end < 0:
        raise ValueError('ROTV directory prefix is unterminated or exceeds its limit')
    prefix = data[start:end].decode('ascii')
    if prefix:
        prefix = _safe_name(prefix)
        if not all(row['path'].casefold().startswith(prefix.casefold() + '/') for row in rows):
            raise ValueError('ROTV directory prefix does not contain every indexed path')
    at = end + 1
    files = len(rows)
    # Check the whole extent before reading records or allocating metadata.
    if len(data) - at != 16 + 2 * (8 + 16 * files):
        raise ValueError('ROTV suffix size disagrees with two file-count arrays')
    if data[at:at + 16] != bytes(16):
        raise ValueError('Unverified nonzero ROTV reserved bytes')
    at += 16
    arrays = []
    for number in range(2):
        tag, count = struct.unpack_from('>4sI', data, at)
        if tag != b'ROTV' or count != files:
            raise ValueError(f'ROTV array {number + 1} tag/count disagrees with the file table')
        records_at, zero_records = at + 8, 0
        records_end = records_at + 16 * count
        # Parse every record; retain opaque bytes in a JSON-compatible form.
        # A zero record is observed in the first array and is not a missing
        # file reference. Identity still comes only from validated name tables.
        values = []
        for cursor in range(records_at, records_end, 16):
            record = data[cursor:cursor + 16]
            values.append(record.hex())
            zero_records += record == bytes(16)
        arrays.append(dict(tag='ROTV', offset=at, records_offset=records_at,
                           end=records_end, count=count, record_bytes=16,
                           sha256=hashlib.sha256(memoryview(data)[records_at:records_end]).hexdigest(),
                           zero_records=zero_records))
        # Commit entry metadata only after both arrays have passed validation.
        if number == 0:
            first_values = values
        else:
            second_values = values
        at = records_end
    if at != len(data):
        raise ValueError('Unverified bytes after ROTV arrays')
    for row, first, second in zip(rows, first_values, second_values):
        row['rotv_records'] = [first, second]
    trace['rotv_suffix'] = dict(
        grammar='avengers_pc_cc8_v1_rotv_16x2', validated=True,
        directory_prefix=prefix, prefix_bytes=end - start + 1, reserved_bytes=16,
        record_tables=arrays,
        record_semantics='Opaque 16-byte records in file-table order; no checksum algorithm or codec established')


def _diagnostics(data, trace, *, error=None):
    """Keep samples small; ROTV occurrences are observations, not records."""
    within_limit = len(data) <= MAX_INDEX_BYTES
    report = dict(schema='tt.cc-index-diagnostic.v1', index_bytes=len(data),
                  index_sha256=hashlib.sha256(data).hexdigest() if within_limit else None,
                  status='invalid_prefix' if error else 'complete',
                  extraction_allowed=False, prefix_validated=error is None, complete_index_validated=False,
                  phase=trace.get('phase', 'header'), last_read_offset=trace.get('cursor') if error else None,
                  layout=trace.get('layout'), table_spans=trace.get('table_spans', []),
                  offset_basis='Index-relative unless explicitly named source_offset or suffix_offset',
                  scope='Index structure inspection only; this report contains no extractable entries or payload blobs.')
    if not within_limit:
        report['index_hash_omitted_reason'] = 'Rejected index exceeds the configured read/hash limit'
    if error:
        message = str(error)
        report['error'] = message[:MAX_DIAGNOSTIC_ERROR_CHARS]
        report['error_truncated'] = len(message) > MAX_DIAGNOSTIC_ERROR_CHARS
        return report
    start = trace['tables_end']
    report.update(tables_end=start, validated_file_count=trace['validated_file_count'],
                  named_override_count=trace['named_override_count'],
                  zero_path_hash_count=trace['zero_path_hash_count'])
    suffix_bytes = len(data) - start
    report['complete_index_validated'] = not suffix_bytes
    if not suffix_bytes:
        report['phase'] = 'complete'
        return report
    if 'rotv_suffix' in trace:
        report['complete_index_validated'] = True
        report['phase'] = 'complete'
        report['suffix'] = dict(offset=start, bytes=suffix_bytes,
                                sha256=hashlib.sha256(memoryview(data)[start:]).hexdigest(),
                                **trace['rotv_suffix'])
        return report
    report['status'] = 'unsupported_suffix'
    suffix = dict(offset=start, bytes=suffix_bytes,
                  sha256=hashlib.sha256(memoryview(data)[start:]).hexdigest(),
                  first_bytes_hex=bytes(data[start:start + MAX_DIAGNOSTIC_BYTES]).hex(),
                  first_bytes_limit=MAX_DIAGNOSTIC_BYTES,
                  grammar='Unverified; suffix bytes are not accepted as padding or metadata records',
                  tag_candidates=[], tag_candidate_limit=MAX_DIAGNOSTIC_TAGS,
                  tag_candidates_truncated=False)
    cursor = start
    while True:
        cursor = data.find(b'ROTV', cursor)
        if cursor < 0:
            break
        if len(suffix['tag_candidates']) == MAX_DIAGNOSTIC_TAGS:
            suffix['tag_candidates_truncated'] = True
            break
        available = min(4, (len(data) - cursor - 4) // 4)
        # The two interpretations help compare specimens. Neither is labeled
        # a count/length, and no pointer is followed on the basis of a marker.
        suffix['tag_candidates'].append(dict(
            tag='ROTV', offset=cursor, suffix_offset=cursor-start,
            following_u32_be=[struct.unpack_from('>I', data, cursor + 4 + i*4)[0] for i in range(available)],
            following_u32_le=[struct.unpack_from('<I', data, cursor + 4 + i*4)[0] for i in range(available)],
            interpretation='Unclassified marker candidate; not a decoded record'))
        cursor += 4
    report['suffix'] = suffix
    if 'suffix_error' in trace:
        suffix['validation_error'] = trace['suffix_error'][:MAX_DIAGNOSTIC_ERROR_CHARS]
    report['next_step'] = ('Compare these offsets, table spans and bounded observations with at least two original '
                           'indexes and an independent format reference. Implement and negatively test the additional '
                           'grammar before enabling extraction; do not skip the suffix or infer padding from ROTV.')
    return report


def _parse_with_diagnostics(data, archive_limit=None, *, expected_layout=None):
    trace = {}
    try:
        rows = _parse_tables(data, archive_limit, expected_layout=expected_layout, trace=trace)
    except ValueError as error:
        raise CCIndexError(str(error), _diagnostics(data, trace, error=error)) from error
    try:
        _parse_rotv_suffix(data, rows, trace)
    except ValueError as error:
        # The prefix remains valid, but incomplete/malformed extension framing
        # cannot expose entries. Keep this distinct from a corrupt name table.
        trace['suffix_error'] = str(error)
    return rows, _diagnostics(data, trace)


def parse_index(data, archive_limit=None, *, expected_layout=None):
    rows, report = _parse_with_diagnostics(data, archive_limit, expected_layout=expected_layout)
    if report['status'] == 'unsupported_suffix':
        layout, suffix = report['layout'], report['suffix']
        raise CCIndexError(
            f"Unverified bytes after CC8 index tables: kind {layout['kind']} / version {layout['version']}, "
            f"tables end at 0x{suffix['offset']:x}; {suffix['bytes']} additional bytes. "
            'Extraction remains blocked. Run formats/cu3/scripts/inspect_archive_cc.py for bounded diagnostics.', report)
    return rows


def diagnose_index(data, archive_limit=None, *, expected_layout=None):
    """Inspect known table structure without returning extraction entries.

    Only the observed (-8, 1) ROTV framing is accepted. Other tails remain
    unsupported; no decoder dispatch or pointer traversal uses these records.
    """
    try:
        _, report = _parse_with_diagnostics(data, archive_limit, expected_layout=expected_layout)
        return report
    except CCIndexError as error:
        return error.diagnostics


def _source_stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_index(path):
    """Read only the bounded index, with metadata from the same open handle.

    Comparing handle metadata avoids Windows directory-cache timestamps and
    catches a source rewritten or truncated while the index is being read.
    This is a read-time check, not a lock against later changes to the archive.
    """
    path = Path(path)
    is_header = path.suffix.lower() == '.hdr'
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if is_header:
            offset, size = 0, before.st_size
            if not 32 <= size <= MAX_INDEX_BYTES:
                raise ValueError('CC archive header exceeds size limit')
        else:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError('Truncated DAT archive header')
            offset, size = struct.unpack('<II', header)
            if offset & 0x80000000:
                offset = ((offset ^ 0xffffffff) << 8) + 0x100
            if offset < 8 or not 32 <= size <= MAX_INDEX_BYTES or offset + size > before.st_size:
                raise ValueError('CC8 index lies outside archive')
            stream.seek(offset)
        data = stream.read(size)
        after = os.fstat(stream.fileno())
    if _source_stamp(before) != _source_stamp(after):
        raise ValueError('CC archive changed while its index was read')
    if len(data) != size:
        raise ValueError('CC archive index could not be read completely')
    source = dict(name=path.name, kind='hdr' if is_header else 'dat', bytes=before.st_size,
                  index_offset=offset, index_bytes=size,
                  archive_extent_check='unavailable for a detached HDR' if is_header else 'checked against data before index',
                  read_identity=dict(device=before.st_dev, inode=before.st_ino,
                                     mtime_ns=before.st_mtime_ns, ctime_ns=before.st_ctime_ns))
    return data, None if is_header else offset, source


def _add_source(report, source):
    report['source'] = source
    if 'suffix' in report:
        suffix = report['suffix']
        suffix['source_offset'] = source['index_offset'] + suffix['offset']
        for candidate in suffix.get('tag_candidates', []):
            candidate['source_offset'] = source['index_offset'] + candidate['offset']
        for table in suffix.get('record_tables', []):
            table['source_offset'] = source['index_offset'] + table['offset']
            table['records_source_offset'] = source['index_offset'] + table['records_offset']
    return report


def index(path, *, expected_layout=None):
    data, archive_limit, source = _read_index(path)
    try:
        return parse_index(data, archive_limit=archive_limit, expected_layout=expected_layout)
    except CCIndexError as error:
        _add_source(error.diagnostics, source)
        raise


def diagnose_archive(path, *, expected_layout=None):
    """Return bounded index metadata from an explicit DAT/HDR path, never files."""
    data, archive_limit, source = _read_index(path)
    return _add_source(diagnose_index(data, archive_limit, expected_layout=expected_layout), source)
