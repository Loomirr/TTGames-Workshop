"""Reader for TT Games .DAT archives: LEGO Batman 1 PC (MkDat V3.26, index version -2) and
LEGO Marvel Super Heroes PC (PakDat v1.01, index version -5; 12-byte name records, plain index offset),
and LEGO Star Wars: The Complete Saga PC (index version -3: plain index offset),
and LEGO Batman 2: DC Super Heroes PC (PakDat v1.01, index version -4; see below).

Layout (worked out from the files themselves, see EXTRACTION.md):
  u32 a, u32 info_size            a is negative-encoded: info_off = ((~a) << 8) + 0x100
  @info_off:
    i32 version (-2), i32 file_count
    file_count * { u32 off_hi, u32 zsize, u32 size, u32 flags }   offset = (off_hi << 8) | (flags >> 8 & 0xff)
                                                                   flags & 0xff = compression (0 none, 2 LZ2K)
    i32 name_count
    name_count * { i16 next, i16 prev, i32 name_off }
        next > 0  -> directory;  next <= 0 -> file with index -next
        prev != 0 -> sibling of record prev;  prev == 0 -> first child of the preceding directory record
    i32 names_size, names blob (NUL-terminated strings)
    file_count * u32 crc (not needed here)

Index version -4 (LEGO Batman 2, measured on all 11,865 entries of its four archives): index offset stored
plainly; 16-byte file records and 8-byte name records as in -2; a file's offset is off_hi << 8 ALONE (every file
starts on a 512-byte boundary; bytes 1 and 2 of the flags word hold something else, not known, and must not be
added); a name record's -next is the file's index directly, and that index is also its position in the sorted
table of path hashes at the end of the index (the -3 hash; both ways agree for every entry); the index ends with
8 zero bytes after that table. Compression met: 0 (stored) and 2 (LZ2K) only.

Usage:
    python tools/ttdat.py list  <archive.dat> [substring]
    python tools/ttdat.py stats <archive.dat>
    python tools/ttdat.py extract <archive.dat> <out_dir> [substring ...]   (case-insensitive path filters)
                                                 add --missing to write only files not already extracted
"""
import os
import struct
import sys
from collections import Counter


class DatEntry:
    __slots__ = ("path", "offset", "zsize", "size", "comp")

    def __init__(self, path, offset, zsize, size, comp):
        self.path, self.offset, self.zsize, self.size, self.comp = path, offset, zsize, size, comp


class DatArchive:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        a, info_size = struct.unpack("<II", self.f.read(8))
        if a & 0x80000000:
            info_off = ((a ^ 0xFFFFFFFF) << 8) + 0x100
        else:
            info_off = a
        self.f.seek(info_off)
        info = self.f.read(info_size)
        self.version, count = struct.unpack_from("<ii", info, 0)
        # -2: LEGO Batman 1 (2008). -5: LEGO Marvel Super Heroes (2013), header text "PakDat v1.01":
        # identical except that the index offset is stored plainly and each name record has 4 extra (zero) bytes.
        # -3: LEGO Star Wars: The Complete Saga (2007 engine, PC 2009): as -2, but the index offset is stored plainly and names
        # find their files through the hash table (verified: all 12,174 names of GAME.DAT hit the table).
        # -4: LEGO Batman 2: DC Super Heroes (2012), header text "PakDat v1.01": plain index offset, records as -2,
        # but the file offset is off_hi << 8 with no low byte from the flags word (see the docstring).
        rec_size = {-2: 8, -3: 8, -4: 8, -5: 12}.get(self.version)
        if rec_size is None:
            raise ValueError(f"{path}: index version {self.version} not handled (-2, -3, -4 and -5 verified)")
        raw = [struct.unpack_from("<IIII", info, 8 + i * 16) for i in range(count)]
        pos = 8 + count * 16
        (name_count,) = struct.unpack_from("<i", info, pos)
        pos += 4
        recs = [struct.unpack_from("<hhi", info, pos + i * rec_size) for i in range(name_count)]
        pos += name_count * rec_size
        (names_size,) = struct.unpack_from("<i", info, pos)
        blob = info[pos + 4:pos + 4 + names_size]

        def name_at(off):
            end = blob.index(b"\0", off)
            return blob[off:end].decode("latin1")

        by_hash = None
        if self.version == -3:
            hashes = struct.unpack_from("<%dI" % count, info, pos + 4 + names_size)
            by_hash = {h: i for i, h in enumerate(hashes)}
        paths = [None] * count
        parent = [""] * name_count  # directory path each record lives in
        full = [""] * name_count
        last_dir = 0
        for i, (nxt, prev, noff) in enumerate(recs):
            if i == 0:
                full[0] = ""
                last_dir = 0
                continue
            if prev != 0:
                parent[i] = parent[prev]
            else:
                parent[i] = full[last_dir]
            name = name_at(noff)
            full[i] = (parent[i] + "\\" + name) if parent[i] else name
            if nxt > 0:
                last_dir = i
            elif by_hash is not None:
                # -3: the file records are sorted by a hash of the upper-case path (the table at the end of the
                # index); a name finds its file through that hash, not through the number in its record
                h = 0x811C9DC5
                for ch in full[i].upper().encode("latin1"):
                    h = ((h ^ ch) * 0x199933) & 0xFFFFFFFF
                if h in by_hash:
                    paths[by_hash[h]] = full[i]
            else:
                paths[-nxt] = full[i]
        self.entries = []
        for i, (off_hi, zsize, size, flags) in enumerate(raw):
            offset = (off_hi << 8) if self.version == -4 else (off_hi << 8) | ((flags >> 8) & 0xFF)
            self.entries.append(DatEntry(paths[i] or f"__unnamed_{i}", offset, zsize, size, flags & 0xFF))

    def read_raw(self, e):
        self.f.seek(e.offset)
        return self.f.read(e.zsize)

    def read(self, e):
        data = self.read_raw(e)
        if e.comp == 0:
            return data
        if e.comp == 2:
            from lz2k import decompress_chunked
            out = decompress_chunked(data)
            if len(out) != e.size:
                raise ValueError(f"{e.path}: decompressed {len(out)} bytes, index says {e.size}")
            return out
        raise ValueError(f"{e.path}: unknown compression {e.comp}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, arc = argv[0], DatArchive(argv[1])
    if cmd == "list":
        filt = argv[2].lower() if len(argv) > 2 else ""
        for e in arc.entries:
            if filt in e.path.lower():
                print(f"{e.size:>10} {e.zsize:>10} c{e.comp} {e.path}")
    elif cmd == "stats":
        comp = Counter(e.comp for e in arc.entries)
        ext = Counter(os.path.splitext(e.path)[1].lower() for e in arc.entries)
        top = Counter(e.path.split("\\")[0].lower() for e in arc.entries if "\\" in e.path)
        magic = Counter()
        for e in arc.entries:
            if e.comp:
                arc.f.seek(e.offset)
                magic[arc.f.read(4)] += 1
        print(f"{arc.path}: {len(arc.entries)} files, {sum(e.size for e in arc.entries)} bytes unpacked")
        print(" compression:", dict(comp), " compressed magics:", dict(magic))
        print(" top dirs:", dict(top))
        print(" extensions:", dict(ext.most_common()))
    elif cmd == "extract":
        only_missing = "--missing" in argv   # skip files already on disk at the right size (re-run after a fix)
        out_dir, filters = argv[2], [a.lower() for a in argv[3:] if a != "--missing"]
        n = failed = 0
        for e in arc.entries:
            if filters and not any(fl in e.path.lower() for fl in filters):
                continue
            dest = os.path.join(out_dir, e.path)
            if only_missing and os.path.exists(dest) and os.path.getsize(dest) == e.size:
                continue
            os.makedirs(os.path.dirname(dest) or out_dir, exist_ok=True)
            try:
                data = arc.read(e)
            except Exception as ex:  # keep going, report at the end
                failed += 1
                print("FAILED", e.path, ex)
                continue
            with open(dest, "wb") as o:
                o.write(data)
            n += 1
        print(f"extracted {n} files to {out_dir}, {failed} failed")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
