"""LSW1 PC ANI/BSA record inspection and same-layout channel edits.

Derived from original PC samples and isolated native scalar evaluation. No
later AN3/AN4 reader is used. This does not bind tracks to a rig or face.
Addresses, time records, lookup tables, flags and unknown bytes stay intact.
"""
from collections import Counter
from bisect import bisect_left, bisect_right
import hashlib
import math
import struct


class AnimationError(ValueError):
    pass


class AnimationRecords:
    MAX_BYTES = 64 * 1024 * 1024
    MAX_CHANNELS = 65536

    def __init__(self, data, family):
        if family not in ('ANI', 'BSA'):
            raise AnimationError('Select the LSW1 PC ANI or BSA profile explicitly')
        if not 40 <= len(data) <= self.MAX_BYTES:
            raise AnimationError('Animation size is outside the supported bounds')
        self.data = bytes(data)
        self.family = family
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        self.regions = []
        self.records = []
        self.aliases = False
        self._curves = {}
        if self.u32(0) != 2:
            raise AnimationError('Expected the observed LSW1 PC record tag 2')
        self.base = self.u32(4)
        delta = 0 if family == 'ANI' else 4
        header_end = 36 + delta
        self.claim(0, header_end, 'header')
        if self.pointer(8) != 12 + delta:
            raise AnimationError('Unsupported animation root pointer')
        if family == 'BSA' and self.u32(12) != 0:
            raise AnimationError('Unsupported BSA header word at 0x0C')
        self.duration = self.float(12 + delta)
        self.tracks, self.components = struct.unpack_from('<HH', self.data, 16 + delta)
        count = self.tracks * self.components
        if not 0 < count <= self.MAX_CHANNELS or (family == 'ANI' and self.components != 9):
            raise AnimationError('Unsupported track/component count')
        self.blocks = self.u32(20 + delta)
        if not 1 < self.duration <= 65536 or self.blocks != math.ceil((self.duration - 1) / 32):
            raise AnimationError('Unsupported duration/block table relationship')
        values, types, flags = [self.pointer(p + delta) for p in (24, 28, 32)]
        if values != (36 if family == 'ANI' else 48):
            raise AnimationError('Unsupported value table position')
        self.claim(values, count * 4, 'values')
        self.claim(types, count, 'types')
        self.claim(flags, self.tracks, 'track flags')
        self.flags = self.data[flags:flags + self.tracks]
        for index in range(count):
            kind = self.data[types + index]
            slot = values + index * 4
            if kind == 0:
                record = dict(kind=0, slot=slot, value=self.float(slot))
            elif kind in (1, 2):
                address = self.pointer(slot)
                if address in self._curves:
                    prior = self._curves[address]
                    if prior['kind'] != kind:
                        raise AnimationError('One curve is referenced with conflicting types')
                    self.aliases = True
                    record = prior
                else:
                    record = self.read_curve(address, kind, index)
                    self._curves[address] = record
            else:
                raise AnimationError(f'Unsupported curve type {kind} at channel {index}')
            self.records.append(record)
        # Regions may be physically unordered, but never overlap. Shared whole
        # curves are recorded once above and refused by the editor below.
        ordered = sorted(self.regions)
        for left, right in zip(ordered, ordered[1:]):
            if left[1] > right[0]:
                raise AnimationError(f'Overlapping animation regions: {left[2]} / {right[2]}')

    def require(self, offset, size, label):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise AnimationError(f'{label} lies outside the animation')

    def claim(self, offset, size, label):
        self.require(offset, size, label)
        if size:
            entry = (offset, offset + size, label)
            index = bisect_left(self.regions, entry)
            if (index and self.regions[index - 1][1] > offset) or (
                    index < len(self.regions) and self.regions[index][0] < offset + size):
                raise AnimationError(f'Overlapping animation region: {label}')
            self.regions.insert(index, entry)

    def u32(self, offset):
        self.require(offset, 4, 'integer')
        return struct.unpack_from('<I', self.data, offset)[0]

    def pointer(self, offset):
        value = self.u32(offset) - self.base
        self.require(value, 0, 'serialized pointer')
        return value

    def float(self, offset):
        self.require(offset, 4, 'float')
        value = struct.unpack_from('<f', self.data, offset)[0]
        if not math.isfinite(value):
            raise AnimationError(f'Non-finite animation value at 0x{offset:X}')
        return value

    def read_curve(self, address, kind, index):
        label = f'channel {index}'
        self.claim(address, 12, label + ' curve header')
        masks, prefixes, payload = [self.pointer(address + p) for p in (0, 4, 8)]
        if payload != address + 12 or prefixes != masks + self.blocks * 4:
            raise AnimationError('Unsupported curve table positions')
        start = payload + (8 if kind == 2 else 0)
        stride = 16 if kind == 1 else 4
        if masks <= start or (masks - start) % stride:
            raise AnimationError('Invalid curve key span')
        count = (masks - start) // stride
        self.claim(payload, masks - payload, label + ' keys')
        self.claim(masks, self.blocks * 4, label + ' masks')
        self.claim(prefixes, self.blocks * 2, label + ' prefixes')
        bits = []
        for block in range(self.blocks):
            prefix = struct.unpack_from('<H', self.data, prefixes + block * 2)[0]
            if prefix != len(bits):
                raise AnimationError('Curve lookup prefix disagrees with its masks')
            mask = self.u32(masks + block * 4)
            bits.extend(block * 32 + bit for bit in range(32) if mask & (1 << bit))
        if not bits or len(bits) > count:
            raise AnimationError('Curve masks reference missing keys')
        keys = []
        if kind == 2:
            tangent_scale, value_scale = self.float(payload), self.float(payload + 4)
        for key in range(count):
            at = start + key * stride
            if kind == 1:
                time, reciprocal, value, tangent = [self.float(at + n * 4) for n in range(4)]
                keys.append(dict(at=at, stored_time=time, reciprocal=reciprocal,
                                 value=value, tangent=tangent))
            else:
                value, tangent, time = struct.unpack_from('<hbB', self.data, at)
                keys.append(dict(at=at, stored_time=time, quantized_value=value,
                                 quantized_tangent=tangent, value=value * value_scale,
                                 tangent=tangent * tangent_scale))
        return dict(kind=kind, address=address, payload=payload, keys=keys,
                    mask_frames=bits, extra_keys=count - len(bits))

    def summary(self):
        curves = [r for r in self.records if r['kind']]
        disagreements = sum(any((key['stored_time'] - 1 if r['kind'] == 1 else key['stored_time'])
                                != (frame if r['kind'] == 1 else frame % 256)
                                for key, frame in zip(r['keys'], r['mask_frames'])) for r in curves)
        return dict(family=self.family, sha256=self.sha256, bytes=len(self.data),
                    duration=self.duration, tracks=self.tracks, components=self.components,
                    curve_types=dict(Counter(r['kind'] for r in self.records)),
                    keys=sum(len(r['keys']) for r in curves),
                    extra_keys=sum(r['extra_keys'] for r in curves),
                    shared_curves=self.aliases,
                    key_time_mask_disagreements=disagreements,
                    uninterpreted_bytes=len(self.data) - sum(b-a for a,b,_ in self.regions),
                    scope='Record inspection; no rig ownership, playback or in-game validation')

    def evaluate_channel(self, track, component, time):
        """Evaluate one scalar using the observed PC curve routine's rules.

        Time is one-based native frame time, not seconds. Masks select the key
        pair; stored times and tangents determine the cubic. Extra keys and
        time/mask disagreements are retained, not sorted or silently repaired.
        This does not establish which bone or facial target owns a channel.
        """
        if not isinstance(track, int) or not isinstance(component, int) or not (
                0 <= track < self.tracks and 0 <= component < self.components):
            raise AnimationError('Track/component is outside this animation')
        if not isinstance(time, (int, float)) or not math.isfinite(time):
            raise AnimationError('Animation time must be finite')

        def f32(value):
            try:
                result = struct.unpack('<f', struct.pack('<f', value))[0]
            except (OverflowError, struct.error) as error:
                raise AnimationError('Evaluated curve exceeds float32 range') from error
            if not math.isfinite(result):
                raise AnimationError('Evaluated curve is not finite')
            return result

        time = f32(time)
        if time >= self.duration:
            time = f32(self.duration - f32(.01))
        time = max(1., time)
        record = self.records[track * self.components + component]
        if record['kind'] == 0:
            return record['value']
        index = bisect_right(record['mask_frames'], int(time) - 1) - 1
        if index < 0 or index + 1 >= len(record['keys']):
            raise AnimationError('Curve lookup has no bounded interpolation pair at this time')
        first, second = record['keys'][index:index + 2]
        dt = second['stored_time'] - first['stored_time']
        if record['kind'] == 1:
            u = (time - first['stored_time']) * first['reciprocal']
        else:
            # The native byte-time form uses its stored interval directly,
            # including zero and negative intervals; it does not unwrap bytes.
            u = f32((time - 1. - first['stored_time']) * (1. / dt if dt else 0.))
        m0 = f32(first['tangent'] * dt)
        m1 = f32(second['tangent'] * dt)
        v0, v1 = first['value'], second['value']
        d = v0 - v1
        value = (((2. * d + m0 + m1) * u - 3. * d - 2. * m0 - m1) * u + m0) * u + v0
        return f32(value)

    def transform_channel(self, track, component, *, scale=1.0, offset=0.0, expected_sha256):
        """Return a separate byte string with one channel's values transformed.

        Tangents scale with values. Compressed offsets must fit the existing
        quantization range; duration, time records and topology never change.
        This is a research editor, not an arbitrary animation exporter.
        """
        if expected_sha256 != self.sha256:
            raise AnimationError('Source hash differs from the inspected animation')
        if not isinstance(track, int) or not isinstance(component, int) or not (
                0 <= track < self.tracks and 0 <= component < self.components):
            raise AnimationError('Track/component is outside this animation')
        if not math.isfinite(scale) or not math.isfinite(offset):
            raise AnimationError('Scale and offset must be finite')
        if scale == 1 and offset == 0:
            return self.data
        if self.aliases:
            raise AnimationError('Editing shared curves is not supported')
        record = self.records[track * self.components + component]
        result = bytearray(self.data)

        def put_float(at, value):
            try:
                encoded = struct.pack('<f', value)
            except (OverflowError, struct.error) as error:
                raise AnimationError('Edited value exceeds float32 range') from error
            if not math.isfinite(struct.unpack('<f', encoded)[0]):
                raise AnimationError('Edited value is not finite')
            result[at:at+4] = encoded

        if record['kind'] == 0:
            put_float(record['slot'], record['value'] * scale + offset)
        elif record['kind'] == 1:
            for key in record['keys']:
                put_float(key['at'] + 8, key['value'] * scale + offset)
                put_float(key['at'] + 12, key['tangent'] * scale)
        else:
            payload = record['payload']
            put_float(payload, self.float(payload) * scale)
            put_float(payload + 4, self.float(payload + 4) * scale)
            new_scale = struct.unpack_from('<f', result, payload + 4)[0]
            if offset:
                if new_scale == 0:
                    raise AnimationError('Cannot offset a zero-scale compressed channel')
                for key in record['keys']:
                    raw = key['quantized_value'] + offset / new_scale
                    if not math.isfinite(raw):
                        raise AnimationError('Offset exceeds the existing compressed value range')
                    quantized = round(raw)
                    if not -32768 <= quantized <= 32767:
                        raise AnimationError('Offset exceeds the existing compressed value range')
                    struct.pack_into('<h', result, key['at'], quantized)
        # Validate the output with exactly the same profile and bounds checks.
        AnimationRecords(result, self.family)
        return bytes(result)
