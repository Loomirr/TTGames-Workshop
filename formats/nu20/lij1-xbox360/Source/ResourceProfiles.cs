using System.Buffers.Binary;

namespace Lij1Textures;

public static partial class Extractor
{
    public static readonly string[] InputExtensions = [".ghg", ".gsc", ".tex", ".fnt", ".dds"];
    static int Units(int pixels, int unit) => Math.Max(1, (pixels + unit - 1) / unit);
    static string FourCc(int format) => format switch { 1 => "DXT1", 3 => "DXT3", 4 => "BC5", 6 => "DXT5", 9 => "RGBA32F", _ => throw new InvalidDataException("Unknown texture format.") };
    static uint GpuFormat(int format) => format switch { 1 => 0x1a200152, 3 => 0x1a200153, 4 => 0x1a200171, 6 => 0x1a200154, 9 => 0x1a22aba6, _ => 0 };
    static int FromGpu(uint word) => word switch { 0x1a200152 => 1, 0x1a200153 => 3, 0x1a200171 => 4, 0x1a200154 => 6, 0x1a22aba6 => 9, _ => throw new InvalidDataException($"Unknown GPU format word 0x{word:X8}.") };
    static void Dimensions(int w, int h) => Require(IsPowerOfTwo(w) && IsPowerOfTwo(h) && w <= 8192 && h <= 8192, "Unsupported texture dimensions.");
    static bool ValidResourceAllocation(int w, int h, int format, int mips, int allocated) =>
        ExpectedAllocation(w, h, format == 1 ? 8 : 16, mips, format == 9 ? 1 : 4) == allocated
        || (format == 1 && mips == 1 && allocated == 4096 && ((w == 32 && h == 32) || (w == 64 && h == 32) || (w == 128 && h == 64)));

    public static ParsedFile ParseInput(byte[] b, string extension)
    {
        Require(b.Length >= 24 && b.Length <= MaxFileBytes, "Invalid file size.");
        if (Tag(b, 0, "02UN"u8)) return Parse(b);
        if (extension.Equals(".dds", StringComparison.OrdinalIgnoreCase)) return ParseDds(b);
        Require(extension.Equals(".tex", StringComparison.OrdinalIgnoreCase) || extension.Equals(".fnt", StringComparison.OrdinalIgnoreCase), "Unknown container or platform layout.");
        int end = checked((int)U32(b, 0));
        Require(end >= 184 && end <= b.Length - 8, "Invalid standalone resource boundary.");
        int count = checked((int)U32(b, end));
        Require(count is >= 1 and <= 4096 && (long)end + 4 + count * 4 == b.Length, "Invalid relocation footer.");
        var relocations = new HashSet<int>();
        for (int j = 0; j < count; j++)
        {
            int at = end + 4 + j * 4;
            long target = (long)at + I32(b, at);
            Require(target >= 4 && target <= end - 4 && (target & 3) == 0 && relocations.Add((int)target), "Invalid relocation entry.");
        }
        bool font = extension.Equals(".fnt", StringComparison.OrdinalIgnoreCase);
        long dLong = font ? 8L + I32(b, 8) : 4;
        Require(dLong >= 4 && dLong <= end - 180, "Invalid font texture pointer.");
        int d = (int)dLong;
        if (font) Require(relocations.Contains(4) && relocations.Contains(8), "Unknown font pointer profile.");
        int w = checked((int)U32(b, d)), h = checked((int)U32(b, d + 4)); Dimensions(w, h);
        int format, mips, bytes, pointer; string profile;
        var warnings = new List<string>();
        if (U32(b, d + 44) == 0x20000000)
        {
            Require(U32(b, d + 80) == 3 && U32(b, d + 84) == 1, "Unknown standalone resource flags.");
            Zero(b, d + 24, 20); Zero(b, d + 48, 8); Zero(b, d + 72, 8); Zero(b, d + 88, 92);
            format = checked((int)U32(b, d + 56)); _ = FourCc(format);
            mips = checked((int)U32(b, d + 64)); bytes = checked((int)U32(b, d + 68));
            pointer = checked(d + 60 + I32(b, d + 60));
            Require(pointer >= d + 180 && pointer <= end, "Invalid standalone payload pointer.");
            Require(relocations.Contains(d + 60), "Missing texture payload relocation.");
            Require(mips >= 1 && mips <= Log2(Math.Max(w, h)) + 1 && ValidResourceAllocation(w, h, format, mips, bytes), "Invalid standalone mip allocation.");
            profile = "standalone-descriptor";
            Zero(b, d + 180, pointer - d - 180);
        }
        else
        {
            // Compact GPU objects occur at two observed field offsets. The footer,
            // rather than a signature search, identifies the stored payload pointer.
            int field = relocations.Contains(d + 28) ? d + 28 : d + 116;
            Require(relocations.Contains(field), "Unknown compact texture pointer profile.");
            Zero(b, d + 8, field - d - 8);
            format = FromGpu(U32(b, field + 8));
            pointer = checked(field + I32(b, field)); bytes = checked((int)U32(b, field + 4));
            Require(pointer >= field + 12 && pointer <= end, "Invalid compact payload pointer.");
            Zero(b, field + 12, pointer - field - 12);
            // These objects have no mip-count field. Export only the unambiguous
            // base image; retain the allocation and explain the limitation.
            mips = 1; profile = "compact-base-image";
            warnings.Add("Compact GPU object has no stored mip count: exported the base image only; remaining allocation is not interpreted as a mip chain.");
            Require(bytes >= (long)Units(w, format == 9 ? 1 : 4) * Units(h, format == 9 ? 1 : 4) * (format == 1 ? 8 : 16), "Compact base image is truncated.");
        }
        Require(pointer >= d + 180 && (pointer & 4095) == 0 && bytes > 0 && (long)pointer + bytes == end, "Invalid standalone payload extent.");
        return new(b, [new(0, d, w, h, Convert.ToHexString(b.AsSpan(d + 8, 16)).ToLowerInvariant(), format, FourCc(format), format == 1 ? 8 : 16, mips, pointer, bytes, profile)], warnings);
    }

    static ParsedFile ParseDds(byte[] b)
    {
        Require(b.Length >= 128 && Tag(b, 0, "DDS "u8) && U32LE(b, 4) == 124 && U32LE(b, 76) == 32, "Invalid DDS header.");
        Require((U32LE(b, 8) & 0x1007) == 0x1007 && U32LE(b, 24) == 0 && (U32LE(b, 108) & 0x1000) != 0,
            "Unsupported DDS flags/depth.");
        int w = checked((int)U32LE(b, 16)), h = checked((int)U32LE(b, 12)); Dimensions(w, h);
        int mips = Math.Max(1, checked((int)U32LE(b, 28)));
        Require(mips <= Log2(Math.Max(w, h)) + 1 && U32LE(b, 112) == 0, "Unsupported DDS surface layout.");
        string code = System.Text.Encoding.ASCII.GetString(b, 84, 4);
        bool compressed = code is "DXT1" or "DXT3" or "DXT5";
        Require(compressed ? U32LE(b, 80) == 4 : U32LE(b, 80) == 0x41 && U32LE(b, 88) == 32
            && U32LE(b, 92) == 0xff0000 && U32LE(b, 96) == 0xff00 && U32LE(b, 100) == 0xff && U32LE(b, 104) == 0xff000000, "Unsupported DDS pixel profile.");
        long expected = 128;
        for (int l = 0; l < mips; l++) expected += compressed ? (long)Blocks(Math.Max(1, w >> l)) * Blocks(Math.Max(1, h >> l)) * (code == "DXT1" ? 8 : 16) : (long)Math.Max(1, w >> l) * Math.Max(1, h >> l) * 4;
        Require(expected == b.Length, "DDS data size disagrees with its header.");
        return new(b, [new(0, 0, w, h, "", -1, compressed ? code : "BGRA8", 0, mips, 0, b.Length, "dds-passthrough")], Array.Empty<string>());
    }

    static bool TryAlignedLegacy(byte[] b, out ParsedFile parsed)
    {
        parsed = null!;
        if (!Tag(b, 16, "DAEH"u8) || U32(b, 20) != 16 || !Tag(b, 32, "LBTN"u8)) return false;
        uint size = U32(b, 36);
        if (size < 12 || size > b.Length - 32 || (size & 15) == 0) return false;
        int tref = checked((32 + (int)size + 15) & ~15), tst = tref + 16;
        if (tref > b.Length - 24) return false;
        if (!Tag(b, tref, "FERT"u8) || U32(b, tref + 4) != 12 || U32(b, tref + 8) != 0 || !Tag(b, tst, "0TST"u8)) return false;
        parsed = ParseAlignedLegacy(b, tst);
        return true;
    }

    static ParsedFile ParseAlignedLegacy(byte[] b, int tst)
    {
        int declared = checked((int)U32(b, tst + 4));
        Require(declared >= 8 && declared <= b.Length - tst, "Invalid legacy TST0 size.");
        var warnings = new List<string> { "Recovered the observed aligned NTBL/TREF envelope with stale chunk lengths; source bytes were preserved." };
        if (declared == 8) return new(b, Array.Empty<TextureEntry>(), warnings);
        int compact = tst + 8;
        if (compact <= b.Length - 52 && U32(b, compact) > 8192 && U32(b, compact + 4) == 0 && U32(b, compact + 8) == 0x1a200152)
        {
            uint dimensions = U32(b, compact);
            int w = (int)(dimensions >> 16), h = (int)(dimensions & 65535); Dimensions(w, h);
            int mips = checked((int)U32(b, compact + 16)), bytes = declared - 60;
            int pointer = checked(compact + 12 + I32(b, compact + 12));
            Zero(b, compact + 20, 32);
            Require(mips == 1 && pointer >= compact + 52 && (pointer & 4095) == 0 && ValidResourceAllocation(w, h, 1, mips, bytes)
                && pointer <= b.Length - bytes - 8 && Tag(b, pointer + bytes, "00SM"u8), "Unknown compact legacy allocation.");
            uint next = U32(b, pointer + bytes + 4);
            Require(next >= 8 && next <= b.Length - pointer - bytes && (next & 7) == 0, "Invalid compact following mesh chunk.");
            return new(b, [new(0, compact, w, h, "", 1, "DXT1", 8, mips, pointer, bytes, "legacy-compact-gpu")], warnings);
        }
        int cursor = tst + 8, first = b.Length, slots = 0;
        var entries = new List<TextureEntry>();
        long declaredPayload = 0;
        while (cursor <= first - 180 && slots < 4096)
        {
            int d = cursor;
            bool little = U32(b, d) > 8192;
            uint Read(int at) => little ? U32LE(b, at) : U32(b, at);
            uint storedW = Read(d), storedH = Read(d + 4);
            if (storedW > 8192 || storedH > 8192) break;
            int w = (int)storedW, h = (int)storedH;
            if (!IsPowerOfTwo(w) || !IsPowerOfTwo(h) || w > 8192 || h > 8192) break;
            bool secondaryOnly = !little && U32(b, d + 44) == 0;
            int format, mips, bytes, pointer, faces = 1;
            string profile;
            if (little || secondaryOnly)
            {
                Zero(b, d + 24, 32); Zero(b, d + 72, 52);
                format = FromGpu(U32(b, d + 136));
                Require(U32(b, d + 124) == GpuFormat(format) && U32(b, d + 128) == ((uint)w << 16 | (uint)h), "Legacy GPU metadata disagrees with dimensions/format.");
                Require(U32(b, d + 132) is 0 or 1, "Unknown legacy surface dimension.");
                faces = U32(b, d + 132) == 1 ? 6 : 1;
                if (little) Require(U32LE(b, d + 56) == GpuFormat(format), "Legacy primary GPU word disagrees.");
                else Zero(b, d + 56, 16);
                mips = checked((int)U32(b, d + 144)); bytes = checked((int)U32(b, d + 148));
                Require(Read(d + 64) == mips && Read(d + 68) == bytes, "Legacy duplicate mip metadata disagrees.");
                pointer = checked(d + 140 + I32(b, d + 140));
                profile = "legacy-secondary-gpu";
            }
            else
            {
                Require((U32(b, d + 44) == 0x08000000 && U32(b, d + 80) == 3 || U32(b, d + 44) == 1 && U32(b, d + 80) == 2)
                    && U32(b, d + 84) == 0, "Unknown aligned descriptor profile.");
                Zero(b, d + 24, 20); Zero(b, d + 48, 8); Zero(b, d + 72, 8); Zero(b, d + 88, 40); Zero(b, d + 132, 4);
                format = checked((int)U32(b, d + 56)); _ = FourCc(format);
                // Earlier TST serializers used code 4 for BC2. The secondary
                // GPU word is authoritative in this explicitly gated profile.
                if (format == 4 && U32(b, d + 136) == 0x1a200153) format = 3;
                mips = checked((int)U32(b, d + 64)); bytes = checked((int)U32(b, d + 68));
                pointer = checked(d + 60 + I32(b, d + 60));
                ValidateSecondary(b, d, w, h, format, mips, bytes, pointer);
                profile = "aligned-secondary-resource";
            }
            Require(pointer >= d + 180 * faces && pointer <= b.Length && (pointer & 4095) == 0, "Invalid legacy secondary payload pointer.");
            Require((mips == 0 && bytes == 0) || (mips >= 1 && mips <= Log2(Math.Max(w, h)) + 1 && bytes > 0), "Invalid legacy mip count/allocation.");
            Require(faces == 1 || (w == h && secondaryOnly), "Unknown legacy cubemap profile.");
            if (faces == 6) Zero(b, d + 180, 900);
            Require(bytes <= b.Length - pointer, "Truncated legacy allocation.");
            if (Tag(b, d + 152, "ADER"u8))
            {
                Require(little && 8L + (slots + faces) * 180 + declaredPayload + bytes == declared && U32(b, d + 156) == 0 && U32LE(b, d + 160) == 3, "Unknown legacy relocation tail.");
                for (int at = d + 164; at < d + 180; at += 4)
                    Require(U32LE(b, at) * 4L >= tst + 8 && U32LE(b, at) * 4L < d + 180, "Invalid legacy relocation-tail index.");
            }
            else Zero(b, d + 152, 28);
            entries.Add(new(entries.Count, d, w, h, Convert.ToHexString(b.AsSpan(d + 8, 16)).ToLowerInvariant(), format, FourCc(format), format == 1 ? 8 : 16, mips, pointer, bytes, profile, faces));
            first = Math.Min(first, pointer); cursor += 180 * faces; slots += faces;
            declaredPayload += bytes;
            if (8L + slots * 180 + declaredPayload == declared) break;
        }
        Require(entries.Count > 0 && cursor <= first, "No bounded legacy texture table.");
        int end = entries.Max(t => checked(t.PayloadOffset + t.PayloadBytes));
        Require(end <= b.Length - 8 && Tag(b, end, "DXAT"u8), "No verified chunk at the legacy payload boundary.");
        uint nextSize = U32(b, end + 4);
        Require(nextSize >= 8 && nextSize <= b.Length - end && (nextSize - 8) % 16 == 0, "Invalid following legacy DXAT chunk.");
        var ordered = entries.OrderBy(t => t.PayloadOffset).ToArray();
        for (int j = 0; j < ordered.Length; j++)
        {
            var t = ordered[j]; int boundary = j + 1 < ordered.Length ? ordered[j + 1].PayloadOffset : end;
            Require(boundary > t.PayloadOffset, "Overlapping legacy payload pointers.");
            int bytes = t.PayloadBytes, mips = t.MipCount;
            if (bytes == 0)
            {
                bytes = boundary - t.PayloadOffset; mips = 1;
                int unit = t.FormatCode == 9 ? 1 : 4;
                Require(bytes / t.Faces >= (long)Units(t.Width, unit) * Units(t.Height, unit) * t.BlockBytes,
                    "Legacy base image cannot fit within its pointer-bounded allocation.");
                declaredPayload += bytes;
                warnings.Add($"Texture {t.Index} has zero mip/allocation metadata: its pointer-bounded base image was exported; no mip chain was inferred.");
            }
            else
            {
                Require(t.PayloadOffset + bytes <= boundary, "Overlapping legacy allocations.");
                Require(boundary - t.PayloadOffset - bytes == ((4096 - (bytes & 4095)) & 4095), "Unknown legacy payload gap.");
                Require(ValidResourceAllocation(t.Width, t.Height, t.FormatCode, mips, bytes)
                    || (t.FormatCode == 1 && t.Width == 32 && t.Height == 32 && mips == 1 && bytes == 2048), "Unknown legacy mip allocation.");
            }
            entries[t.Index] = t with { PayloadBytes = bytes, MipCount = mips, PackedMips = t.MipCount != 0 };
        }
        Require(8L + slots * 180 + declaredPayload == declared, "Legacy logical TST0 size disagrees with its descriptor/resource table.");
        // This profile duplicates source bytes before the aligned payload. It is
        // deliberately not treated as the zero padding of modern containers.
        return new(b, entries, warnings);
    }
}
