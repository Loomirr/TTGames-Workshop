"""Reader for TT Games .giz gizmo placement files (LEGO Batman 1, LEGO Indiana Jones 1, LEGO Star Wars: TCS, PC).

File layout (measured on all 525 .giz files of the three games, see `scan`):
    u32 file version (always 1)
    sections, each:  u32 name_len (1..64), name (not NUL-terminated), u32 body_size, body
    u32 0            end marker (a name_len of 0). 520 files have it; 2 old Batman files simply end after
                     their last section. Nothing follows the marker.
    Not readable: 2 TCS files that are nothing but zero bytes (version 0), and 1 TCS file cut off inside its
    GizmoPickup section.

Section headers (the start of a body; a body may also be empty, 0 bytes):
    u8 version, u16 count          GizObstacle, GizBuildit, GizForce, GizTurret, BombGenerator, GizDig
    u32 version, u16 count         GizFlock
    u8 version, u8 ?, f32 ...      ShadowEditor (one settings block, no count; its size depends on the version)
    u32 version, u32 count         every other section

GizmoPickup body:
    version 4:      u32 version, u32 count, u32 ?                       (12 bytes), then count * 23 bytes
    version 5, 7:   u32 version, u32 count, u32 ?, f32 (10.0), f32 (1.0) (20 bytes), then count * 23 bytes
    version 6:      only seen empty (20-byte header, count 0); a table with records is rejected
    record (same in 4, 5, 7): char name[8], f32 x, f32 y, f32 z, u8 type_letter, u8 flags, u8 ?
    Two TCS files hold a run of records overwritten with unrelated editor data inside a correctly framed table;
    those records are returned with "valid": False.

Sections whose records are a fixed size and start with char name[16], f32 x, y, z are listed in FIXED_RECORDS
and read by `records`; the bytes after the position are returned undecoded. Everything else is kept raw.

Usage:
    python tools/giz.py sections <file.giz>
    python tools/giz.py pickups <file.giz> [out.json]
    python tools/giz.py records <file.giz> <section name>
"""
import json
import math
import struct
import sys
from collections import Counter

FILE_VERSIONS = (1,)

# Type letters seen in GizmoPickup. Meaning is confirmed in GAME_STUDY.md (values come from the exe / capture).
PICKUP_TYPES = {"s": "stud_silver", "g": "stud_gold", "b": "stud_blue", "p": "stud_purple_or_power",
                "m": "minikit", "r": "red_brick", "h": "heart"}
# Every letter that occurs in an intact table of the three games (c, u, e, z: meaning not known).
PICKUP_LETTERS = "sgbpmrhcuez"
# GizmoPickup version -> header size in bytes. Version 6 is handled apart (only empty tables exist).
PICKUP_HEADER = {4: 12, 5: 20, 7: 20}
PICKUP_RECORD = 23
POS_LIMIT = 5000.0      # game units; the largest coordinate of any intact pickup is far below this

HEADER_U8_U16 = ("GizObstacle", "GizBuildit", "GizForce", "GizTurret", "BombGenerator", "GizDig")
HEADER_U32_U16 = ("GizFlock",)
HEADER_NO_COUNT = ("ShadowEditor",)

# (section, version) -> (header size, record size). Every body of that section and version in the three games
# has exactly header + count * record bytes, and every record starts with a printable name[16] and a position.
FIXED_RECORDS = {
    ("Attracto", 3): (8, 31),
    ("BombGenerator", 1): (3, 58),
    ("Grapple", 10): (8, 61),
    ("Lever", 6): (8, 54), ("Lever", 7): (8, 55), ("Lever", 9): (8, 58),
    ("Plug", 2): (8, 35), ("Plug", 3): (8, 36), ("Plug", 4): (8, 37), ("Plug", 5): (8, 39), ("Plug", 6): (8, 43),
    ("SecurityDoor", 3): (8, 40),
    ("Shard", 2): (8, 32),
    ("TightRope", 2): (8, 50), ("TightRope", 4): (8, 75),
    ("Tube", 2): (8, 37), ("Tube", 3): (8, 38),
    ("Whipper", 4): (8, 56),
    ("ZipUp", 2): (8, 60), ("ZipUp", 4): (8, 62), ("ZipUp", 6): (8, 65),
}


class GizError(ValueError):
    """The file (or a section of it) is not in a layout this reader has been checked against."""


def scan(data):
    """Account for every byte of a .giz file. Never raises.

    Returns a dict: version (or None), sections [(name, body_offset, size)] that lie fully inside the file,
    end (offset after the last byte understood), terminator (True if the u32 0 end marker is there),
    complete (True if every byte is accounted for), problem (None, or what is wrong and where).
    """
    out = {"version": None, "sections": [], "end": 0, "terminator": False, "complete": False, "problem": None}
    size = len(data)
    if size < 4:
        out["problem"] = f"file is only {size} bytes, no version word"
        return out
    (version,) = struct.unpack_from("<I", data, 0)
    out["version"] = version
    out["end"] = pos = 4
    if version not in FILE_VERSIONS:
        if not any(data):
            out["problem"] = f"file is {size} zero bytes (an empty placeholder, nothing to read)"
        else:
            out["problem"] = f"file version {version} is not supported (checked: {', '.join(map(str, FILE_VERSIONS))})"
        return out
    while True:
        if pos == size:                       # old files: no end marker
            out["complete"] = True
            return out
        if pos + 4 > size:
            out["problem"] = f"{size - pos} stray bytes at offset {pos} (too few for a section)"
            return out
        (n,) = struct.unpack_from("<I", data, pos)
        if n == 0:                            # end marker
            out["terminator"] = True
            out["end"] = pos + 4
            if pos + 4 == size:
                out["complete"] = True
            else:
                out["problem"] = f"{size - pos - 4} bytes after the end marker at offset {pos}"
            return out
        if n > 64 or pos + 8 + n > size:
            out["problem"] = f"bad section name length {n} at offset {pos}"
            return out
        raw = data[pos + 4:pos + 4 + n]
        if any(c < 32 or c > 126 for c in raw):
            out["problem"] = f"section name at offset {pos + 4} is not text"
            return out
        (body_size,) = struct.unpack_from("<I", data, pos + 4 + n)
        body = pos + 8 + n
        name = raw.decode("latin1")
        if body + body_size > size:
            out["problem"] = (f"section {name} at offset {pos} claims {body_size} bytes but only "
                              f"{size - body} are left (file cut off)")
            out["truncated"] = (name, body, body_size)
            return out
        out["sections"].append((name, body, body_size))
        out["end"] = pos = body + body_size


def sections(data):
    """[(name, body_offset, size)] for every section. Raises GizError for an unsupported file version.

    A file that is cut off or has stray bytes still returns the sections that are whole; use `scan` to see
    whether every byte was accounted for.
    """
    info = scan(data)
    if info["version"] not in FILE_VERSIONS:
        raise GizError(info["problem"])
    return info["sections"]


def section_header(data, name, body, size):
    """(version, count) of a section body. count is None where the section has none; (None, None) if empty."""
    if size == 0:
        return None, None
    if name in HEADER_NO_COUNT:
        return data[body], None
    if name in HEADER_U8_U16:
        if size < 3:
            raise GizError(f"{name}: body of {size} bytes is shorter than its 3-byte header")
        return data[body], struct.unpack_from("<H", data, body + 1)[0]
    if name in HEADER_U32_U16:
        if size < 6:
            raise GizError(f"{name}: body of {size} bytes is shorter than its 6-byte header")
        return struct.unpack_from("<IH", data, body)
    if size == 3:                              # two very old Batman files use the short header everywhere
        return data[body], struct.unpack_from("<H", data, body + 1)[0]
    if size < 8:
        raise GizError(f"{name}: body of {size} bytes is shorter than its 8-byte header")
    return struct.unpack_from("<II", data, body)


def _text(raw):
    return raw.split(b"\0")[0].decode("latin1")


def _printable(raw):
    return all(32 <= c < 127 for c in raw.split(b"\0")[0])


def pickup_table(data):
    """The GizmoPickup section in full: dict with version, count, header fields and the pickups.

    Returns None if the file has no GizmoPickup section. Raises GizError for a layout that was not checked.
    """
    info = scan(data)
    if info["version"] not in FILE_VERSIONS:
        raise GizError(info["problem"])
    if info.get("truncated") and info["truncated"][0] == "GizmoPickup":
        raise GizError("GizmoPickup: " + info["problem"])
    for name, body, size in info["sections"]:
        if name != "GizmoPickup":
            continue
        if size < 8:
            raise GizError(f"GizmoPickup: body of {size} bytes is shorter than its header")
        version, count = struct.unpack_from("<II", data, body)
        if version == 6:
            if count != 0 or size != 20:
                raise GizError(f"GizmoPickup version 6 with {count} records ({size} bytes): only empty version 6 "
                               "tables have been seen, the record layout is not verified")
            header = 20
        elif version in PICKUP_HEADER:
            header = PICKUP_HEADER[version]
        else:
            raise GizError(f"GizmoPickup version {version} is not supported (checked: 4, 5, 7; 6 when empty)")
        if size - header != count * PICKUP_RECORD:
            raise GizError(f"GizmoPickup v{version}: unexpected record size ({size - header} bytes for {count} "
                           f"records, expected {PICKUP_RECORD} each after a {header}-byte header)")
        table = {"version": version, "count": count, "header_word": struct.unpack_from("<I", data, body + 8)[0],
                 "header_floats": list(struct.unpack_from("<2f", data, body + 12)) if header == 20 else []}
        base = body + header
        result = []
        for k in range(count):
            r = data[base + k * PICKUP_RECORD:base + (k + 1) * PICKUP_RECORD]
            x, y, z = struct.unpack_from("<3f", r, 8)
            letter = chr(r[20])
            valid = (letter in PICKUP_LETTERS and _printable(r[:8])
                     and all(math.isfinite(v) and abs(v) < POS_LIMIT for v in (x, y, z)))
            result.append({"index": k, "name": _text(r[:8]),
                           "pos": [x, y, z], "type_letter": letter,
                           "type": PICKUP_TYPES.get(letter, "unknown"), "flags": r[21], "byte22": r[22],
                           "valid": valid})
        table["pickups"] = result
        return table
    return None


def pickups(data):
    """(version, [pickup dicts]) from the GizmoPickup section; (None, []) if the file has none."""
    table = pickup_table(data)
    if table is None:
        return None, []
    return table["version"], table["pickups"]


def records(data, section):
    """(version, [records]) of a section listed in FIXED_RECORDS: index, name, pos, rest (hex of the bytes after
    the position, not decoded). Raises GizError if that section and version were not checked."""
    for name, body, size in sections(data):
        if name != section:
            continue
        version, count = section_header(data, name, body, size)
        if version is None:
            return None, []
        if (name, version) not in FIXED_RECORDS:
            if count == 0:
                return version, []
            raise GizError(f"{name} version {version}: record layout not verified")
        header, rec = FIXED_RECORDS[(name, version)]
        if size - header != count * rec:
            raise GizError(f"{name} v{version}: {size - header} bytes for {count} records, expected {rec} each")
        out = []
        for k in range(count):
            r = data[body + header + k * rec:body + header + (k + 1) * rec]
            out.append({"index": k, "name": _text(r[:16]), "pos": list(struct.unpack_from("<3f", r, 16)),
                        "rest": r[28:].hex()})
        return version, out
    return None, []


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    data = open(argv[1], "rb").read()
    try:
        if argv[0] == "sections":
            info = scan(data)
            if info["version"] not in FILE_VERSIONS:
                raise GizError(info["problem"])
            for name, body, size in info["sections"]:
                try:
                    version, count = section_header(data, name, body, size)
                except GizError:
                    version, count = None, None
                head = "" if version is None else f"  v{version}" + ("" if count is None else f" count {count}")
                print(f"{name:<18} body@{body:<6} size {size}{head}")
            if info["complete"]:
                print("end of file reached" + (" (end marker)" if info["terminator"] else " (no end marker)"))
            else:
                print("NOT fully read:", info["problem"])
        elif argv[0] == "pickups":
            version, items = pickups(data)
            print(f"GizmoPickup v{version}: {len(items)} pickups")
            print(" by type:", dict(Counter((i["type"], i["flags"]) for i in items)))
            bad = [i for i in items if not i["valid"]]
            if bad:
                print(f" {len(bad)} records are not pickups (overwritten in the file itself): marked valid false")
            for i in items:
                if i["valid"] and i["type_letter"] not in "sgb":
                    print(f"  {i['type']:<22} flags {i['flags']} {i['name']:<8} at {[round(v, 2) for v in i['pos']]}")
            if len(argv) > 2:
                with open(argv[2], "w") as f:
                    json.dump(items, f, indent=1)
                print(" wrote", argv[2])
        elif argv[0] == "records" and len(argv) > 2:
            version, items = records(data, argv[2])
            print(f"{argv[2]} v{version}: {len(items)} records")
            for i in items:
                print(f"  {i['name']:<16} at {[round(v, 2) for v in i['pos']]}  {i['rest']}")
        else:
            print(__doc__)
            return 1
    except GizError as e:
        print(f"giz.py: {argv[1]}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
