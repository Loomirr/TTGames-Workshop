"""Read observed LSW1 PC effect registrations from a mapped executable image.

This is a research reader, not a game-independent PE scanner. The caller must
check the executable identity. A registration records a candidate effect blob;
several hardware/render paths can register different blobs under the same ID.
"""
import hashlib
import re
import struct


# push eax (device); push imm8 (ID); push imm32 (length); push imm32 (blob);
# mov ecx, imm32 (effect object); call rel32 (effect loader).
REGISTRATION = re.compile(rb'\x50\x6a(.)\x68(.{4})\x68(.{4})\xb9(.{4})\xe8(.{4})', re.S)
EFFECT_SIGNATURE = b'\x01\x09\xff\xfe'


def registrations(image, base, code_start, code_end, shaders=()):
    """Find the observed complete instruction sequence inside a code interval.

    Bounds are image-relative. Shader addresses are absolute virtual addresses
    from the same image's disassembler inventory. Results retain duplicate IDs
    and do not guess which runtime registration branch will execute.
    """
    if not 0 <= code_start < code_end <= len(image):
        raise ValueError('Invalid effect-registration code range')
    programs = []
    for shader in shaders:
        address = int(shader['address'], 16)
        length = shader['bytes']
        if not isinstance(length, int) or length <= 0 or not base <= address < address + length <= base + len(image):
            raise ValueError('Invalid shader range in effect inventory')
        programs.append((address, length))
    records = []
    for match in REGISTRATION.finditer(image, code_start, code_end):
        effect_id = match[1][0]
        length, address, instance = (struct.unpack('<I', match[i])[0] for i in (2, 3, 4))
        destination = base + match.end() + struct.unpack('<i', match[5])[0]
        if destination != 0x52a290:
            continue
        # An imm8 push sign-extends. Observed IDs are positive array indices.
        if effect_id >= 128 or instance != 0x30437b0 + effect_id * 0x194:
            raise ValueError('Invalid effect object/ID in registration')
        offset = address - base
        if length < 8 or length > 1024 * 1024 or not 0 <= offset < offset + length <= len(image):
            raise ValueError('Invalid registered effect blob range')
        blob = image[offset:offset + length]
        if blob[:4] != EFFECT_SIGNATURE:
            raise ValueError('Unsupported registered effect blob signature')
        contained = []
        for shader_address, shader_length in programs:
            overlaps = shader_address < address + length and address < shader_address + shader_length
            if overlaps:
                if not address <= shader_address < shader_address + shader_length <= address + length:
                    raise ValueError('Shader crosses a registered effect boundary')
                contained.append(hex(shader_address))
        records.append(dict(
            call_address=hex(base + match.end() - 5), effect_id=effect_id,
            blob_address=hex(address), bytes=length, sha256=hashlib.sha256(blob).hexdigest(),
            shader_candidates=contained,
            technique_names=sorted({m.group().decode('ascii') for m in re.finditer(rb'TECHNIQUE_[A-Z0-9_]+(?=\0)', blob)}),
            semantics=sorted({m.group().decode('ascii') for m in re.finditer(rb'SEMANTIC_[A-Z0-9_]+(?=\0)', blob)}),
        ))
    return records
