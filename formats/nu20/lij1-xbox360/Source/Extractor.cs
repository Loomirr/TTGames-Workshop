using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Lij1Textures;

public sealed record TextureEntry(int Index, int DescriptorOffset, int Width, int Height,
    string Identifier, int FormatCode, string FourCc, int BlockBytes, int MipCount,
    int PayloadOffset, int PayloadBytes, string DescriptorProfile = "standard", int Faces = 1, bool PackedMips = true,
    bool RawOnly = false);
public sealed record ParsedFile(byte[] Bytes, IReadOnlyList<TextureEntry> Textures,
    IReadOnlyList<string> Warnings);
public sealed record ExportResult(string Source, string OutputDirectory, int TextureCount,
    IReadOnlyList<string> Warnings);

public static partial class Extractor
{
    public const int MaxFileBytes = 512 * 1024 * 1024;
    public const string Version = "0.1.2";
    const int DescriptorBytes = 180;
    static uint U32(byte[] b, int o) => BinaryPrimitives.ReadUInt32BigEndian(b.AsSpan(o, 4));
    static int I32(byte[] b, int o) => BinaryPrimitives.ReadInt32BigEndian(b.AsSpan(o, 4));
    static uint U32LE(byte[] b, int o) => BinaryPrimitives.ReadUInt32LittleEndian(b.AsSpan(o, 4));
    static bool Tag(byte[] b, int o, ReadOnlySpan<byte> tag) =>
        o >= 0 && o <= b.Length - tag.Length && b.AsSpan(o, tag.Length).SequenceEqual(tag);
    static void Zero(byte[] b, int o, int count)
    {
        Require(o >= 0 && count >= 0 && o <= b.Length - count, "Invalid descriptor/padding bounds.");
        Require(b.AsSpan(o, count).IndexOfAnyExcept((byte)0) < 0, "Unknown texture descriptor fields; a new sample is needed.");
    }
    static bool IsPowerOfTwo(int n) => n > 0 && (n & (n - 1)) == 0;
    static int Blocks(int pixels) => Math.Max(1, (pixels + 3) / 4);
    static int Align32(int n) => (n + 31) & ~31;
    static int Log2(int n) => System.Numerics.BitOperations.Log2((uint)n);
    static void Require(bool ok, string message)
    {
        if (!ok) throw new InvalidDataException(message);
    }

    // This parser intentionally accepts the observed LIJ1 Xbox 360 prototype profile only.
    public static ParsedFile Parse(byte[] b)
    {
        Require(b.Length >= 24 && b.Length <= MaxFileBytes, "File is too short or exceeds the 512 MiB limit.");
        Require(b.AsSpan(0, 4).SequenceEqual("02UN"u8), "Not the supported big-endian NU20 prototype container (02UN). PC/NXG files are different.");
        // One on-disc legacy icon has stale chunk lengths and mixed-endian metadata.
        // Recognize its bounded envelope explicitly; never scan arbitrary signatures.
        if (IsLegacyIconEnvelope(b)) return ParseLegacyIcon(b);
        if (TryAlignedLegacy(b, out var recovered)) return recovered;
        int chunk = 16, textureChunk = -1, end = -1;
        while (chunk <= b.Length - 8)
        {
            uint size = U32(b, chunk + 4);
            Require(size >= 8 && size <= b.Length - chunk, $"Invalid chunk size at 0x{chunk:X}.");
            if (b.AsSpan(chunk, 4).SequenceEqual("0TST"u8))
            {
                textureChunk = chunk;
                end = checked(chunk + (int)size);
                break;
            }
            chunk += (int)size;
        }
        Require(textureChunk >= 0, "No supported top-level TST0 texture chunk found.");
        int cursor = textureChunk + 8, firstPayload = end;
        var textures = new List<TextureEntry>();
        while (cursor <= Math.Min(firstPayload, end) - 8 && U32(b, cursor) != 0)
        {
            Require(textures.Count < 4096 && cursor <= Math.Min(firstPayload, end) - DescriptorBytes,
                "Texture descriptor count or descriptor bounds are invalid.");
            int width = checked((int)U32(b, cursor)), height = checked((int)U32(b, cursor + 4));
            Require(IsPowerOfTwo(width) && IsPowerOfTwo(height) && width >= 1 && height >= 1 && width <= 8192 && height <= 8192,
                $"Unsupported dimensions {width}x{height}. This version supports power-of-two textures from 1 through 8192 pixels.");
            uint layout = U32(b, cursor + 84);
            int faces = U32(b, cursor + 44) == 0x10000000 ? 6 : 1;
            Require((U32(b, cursor + 44) == 0x08000000 || faces == 6) && U32(b, cursor + 80) == 3 && layout is 0 or 1,
                $"Unrecognized resource/layout flags in texture {textures.Count}. Refusing to guess a different layout.");
            foreach (var (start, count) in new[] { (24, 20), (48, 4), (72, 8) }) Zero(b, cursor + start, count);
            Require(U32(b, cursor + 52) == (faces == 6 ? 1u : 0u) && (faces == 1 || (width == height && layout == 1)), "Invalid cubemap fields.");
            int format = checked((int)U32(b, cursor + 56));
            Require(format is 1 or 4 or 6 or 9, $"Unsupported texture format code {format} at 0x{cursor + 56:X}. Supported codes: 1 (BC1), 4 (BC5), 6 (BC3), 9 (RGBA32 float).");
            long payloadLong = (long)cursor + 60 + I32(b, cursor + 60);
            int mips = checked((int)U32(b, cursor + 64)), allocated = checked((int)U32(b, cursor + 68));
            Require(mips >= 1 && mips <= Log2(Math.Max(width, height)) + 1, "Invalid mip count.");
            Require(payloadLong >= cursor + DescriptorBytes && payloadLong <= end && (payloadLong & 4095) == 0,
                "Invalid relative payload pointer or alignment.");
            int payload = (int)payloadLong;
            Require(allocated > 0 && allocated <= end - payload, "Texture payload runs outside TST0.");
            int blockBytes = format == 1 ? 8 : 16;
            if (layout == 1) Zero(b, cursor + 88, 92);
            else
            {
                Zero(b, cursor + 88, 40);
                Zero(b, cursor + 132, 4);
                Zero(b, cursor + 152, 28);
                ValidateSecondary(b, cursor, width, height, format, mips, allocated, payload);
            }
            Require(faces == 1 ? ValidResourceAllocation(width, height, format, mips, allocated)
                : mips == 1 && allocated == ExpectedAllocation(width, height, blockBytes, 1) * 6,
                $"Texture {textures.Count} has an unrecognized mip allocation ({allocated} bytes). Refusing to produce a corrupt DDS.");
            firstPayload = Math.Min(firstPayload, payload);
            textures.Add(new(textures.Count, cursor, width, height,
                Convert.ToHexString(b.AsSpan(cursor + 8, 16)).ToLowerInvariant(),
                format, FourCc(format), blockBytes, mips, payload, allocated,
                layout == 0 ? "secondary-resource" : "standard", faces, true,
                format == 1 && width == 128 && height == 64 && mips == 1 && allocated == 4096));
            if (faces == 6)
            {
                Require(cursor + DescriptorBytes * 6 <= firstPayload, "Truncated cubemap descriptor slots.");
                Zero(b, cursor + 180, 180 * 4);
                Zero(b, cursor + 900, 44);
                Require(U32(b, cursor + 944) == 0x10000000, "Unknown cubemap closing slot.");
                Zero(b, cursor + 948, 132);
            }
            cursor += DescriptorBytes * faces;
        }
        Require(cursor <= firstPayload, "Invalid TST0 descriptor bounds.");
        Require(b.AsSpan(cursor, firstPayload - cursor).IndexOfAnyExcept((byte)0) < 0,
            "Texture descriptor padding contains unknown data.");
        int payloadEnd = firstPayload;
        foreach (var t in textures.OrderBy(t => t.PayloadOffset))
        {
            Require(t.PayloadOffset == payloadEnd, "Texture payloads overlap or have an unrecognized gap.");
            payloadEnd = checked(t.PayloadOffset + t.PayloadBytes);
        }
        Require(payloadEnd == end, "Unrecognized trailing data inside TST0.");
        return new(b, textures, textures.Where(t => t.RawOnly).Select(t =>
            $"Texture {t.Index} declares 128x64 BC1 in only 4096 bytes, but the tiled address span is 6144 bytes. Preserved its allocation as .x360.bin; no DDS was fabricated.").ToArray());
    }

    static void ValidateSecondary(byte[] b, int d, int width, int height, int format,
        int mips, int allocated, int payload)
    {
        Require(U32(b, d + 128) == ((uint)width << 16 | (uint)height)
            && U32(b, d + 136) == GpuFormat(format)
            && (long)d + 140 + I32(b, d + 140) == payload
            && U32(b, d + 144) == mips && U32(b, d + 148) == allocated,
            "Secondary texture metadata disagrees with the primary descriptor or uses an unknown format.");
    }

    static bool IsLegacyIconEnvelope(byte[] b) => b.Length >= 0x13c
        && Tag(b, 0x10, "DAEH"u8) && U32(b, 0x14) == 16
        && Tag(b, 0x20, "LBTN"u8) && U32(b, 0x24) == 0x41 && U32(b, 0x28) == 0x35
        && Tag(b, 0x61, "FERT"u8) && U32(b, 0x65) == 12 && U32(b, 0x69) == 0
        && Tag(b, 0x6d, "0TS"u8)
        && Tag(b, 0x70, "FERT"u8) && U32(b, 0x74) == 12 && U32(b, 0x78) == 0
        && Tag(b, 0x80, "0TST"u8);

    static ParsedFile ParseLegacyIcon(byte[] b)
    {
        const int d = 0x88, width = 64, height = 64, mips = 7, allocated = 0xc000;
        Require(U32(b, 0x84) == 8 + DescriptorBytes + allocated
            && U32LE(b, d) == width && U32LE(b, d + 4) == height
            && U32LE(b, d + 56) == 0x1a200154 && U32LE(b, d + 60) == 0x270f0129
            && U32LE(b, d + 64) == mips && U32LE(b, d + 68) == allocated
            && U32(b, d + 124) == 0x1a200154,
            "Unknown mixed-endian legacy icon layout. Refusing recovery.");
        Zero(b, d + 24, 32);
        Zero(b, d + 72, 52);
        Zero(b, d + 132, 4);
        Zero(b, d + 152, 28);
        long pointer = (long)d + 140 + I32(b, d + 140);
        Require(pointer == 0x1000 && pointer + allocated <= b.Length - 8,
            "Legacy icon payload is truncated or has an unknown pointer.");
        int payload = (int)pointer, next = payload + allocated;
        ValidateSecondary(b, d, width, height, 6, mips, allocated, payload);
        Require(ExpectedAllocation(width, height, 16, mips) == allocated
            && Tag(b, next, "DXAT"u8) && U32(b, next + 4) == 24 && next + 24 <= b.Length,
            "Legacy icon allocation has no verified following chunk. Refusing recovery.");
        var texture = new TextureEntry(0, d, width, height,
            Convert.ToHexString(b.AsSpan(d + 8, 16)).ToLowerInvariant(),
            6, "DXT5", 16, mips, payload, allocated, "legacy-mixed-endian-icon");
        return new(b, new[] { texture }, new[] {
            "Recovered textures from the observed legacy icon layout with inconsistent chunk lengths. Verify the exported images." });
    }

    static long ExpectedAllocation(int w, int h, int bytes, int mips, int unit = 4)
    {
        int tail = Math.Max(0, Math.Min(Log2(w), Log2(h)) - 4);
        long size = 0;
        for (int level = 0; level < mips; level++)
        {
            size += (long)Align32(Units(Math.Max(1, w >> level), unit)) * Align32(Units(Math.Max(1, h >> level), unit)) * bytes;
            if (level >= tail) break;
        }
        return size;
    }

    // Address equations adapted from Xenia (BSD-3-Clause). See THIRD_PARTY_NOTICES.txt.
    public static long TiledAddress(int x, int y, int pitch, int logBytes)
    {
        long outer = ((long)(y >> 5) * (pitch >> 5) + (x >> 5)) << 6;
        long inner = (((y >> 1) & 7) << 3) | (x & 7);
        long address = (outer | inner) << logBytes;
        long bank = (y >> 4) & 1;
        long pipe = ((x >> 3) & 3) ^ (((y >> 3) & 1) << 1);
        return ((long)(y & 1) << 4) | (pipe << 6) | (bank << 11) | (address & 15)
            | (((address >> 4) & 1) << 5) | (((address >> 5) & 7) << 8) | ((address >> 8) << 12);
    }

    public static byte[] ConvertTexture(ParsedFile file, TextureEntry t)
    {
        if (t.FormatCode == -1) return (byte[])file.Bytes.Clone();
        if (t.RawOnly) return file.Bytes.AsSpan(t.PayloadOffset, t.PayloadBytes).ToArray();
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream, Encoding.ASCII, true);
        writer.Write("DDS "u8);
        writer.Write(124u);
        int unit = t.FormatCode == 9 ? 1 : 4;
        uint flags = t.FormatCode == 9 ? 0x100fu : 0x81007u;
        writer.Write(flags | (t.MipCount > 1 ? 0x20000u : 0));
        writer.Write(t.Height); writer.Write(t.Width);
        writer.Write(t.FormatCode == 9 ? t.Width * 16 : Blocks(t.Width) * Blocks(t.Height) * t.BlockBytes);
        writer.Write(0); writer.Write(t.MipCount);
        for (int i = 0; i < 11; i++) writer.Write(0);
        writer.Write(32); writer.Write(4); writer.Write(Encoding.ASCII.GetBytes(t.FormatCode is 4 or 9 ? "DX10" : t.FourCc));
        for (int i = 0; i < 5; i++) writer.Write(0);
        writer.Write(t.MipCount > 1 ? 0x401008u : t.Faces == 6 ? 0x1008u : 0x1000u);
        writer.Write(t.Faces == 6 ? 0xfe00u : 0u);
        for (int i = 0; i < 3; i++) writer.Write(0);
        Require(stream.Length == 128, "Internal DDS header size error.");

        if (t.FormatCode is 4 or 9)
        {
            writer.Write(t.FormatCode == 4 ? 83u : 2u); writer.Write(3u);
            writer.Write(t.Faces == 6 ? 4u : 0u); writer.Write(1u); writer.Write(0u);
        }
        int tail = t.MipCount == 1 || !t.PackedMips ? int.MaxValue : Math.Max(0, Math.Min(Log2(t.Width), Log2(t.Height)) - 4);
        int faceBytes = t.PayloadBytes / t.Faces;
        for (int face = 0; face < t.Faces; face++)
        {
        int storage = face * faceBytes;
        for (int level = 0; level < t.MipCount; level++)
        {
            int bw = Units(Math.Max(1, t.Width >> level), unit), bh = Units(Math.Max(1, t.Height >> level), unit);
            int pitch = Align32(bw), x0 = 0, y0 = 0;
            if (level >= tail)
            {
                pitch = Align32(Units(t.Width >> tail, unit));
                int packed = level - tail;
                if (packed < 3)
                {
                    if (t.Width > t.Height) y0 = (16 >> packed) / unit;
                    else x0 = (16 >> packed) / unit;
                }
                else
                {
                    int offset = (Math.Max(t.Width, t.Height) >> tail) >> (packed - 2);
                    if (t.Width > t.Height) x0 = offset / unit;
                    else y0 = offset / unit;
                }
            }
            byte[] linear = new byte[checked(bw * bh * t.BlockBytes)];
            for (int y = 0; y < bh; y++)
            for (int x = 0; x < bw; x++)
            {
                long relative = storage + TiledAddress(x + x0, y + y0, pitch, t.BlockBytes == 8 ? 3 : 4);
                Require(relative >= face * faceBytes && relative + t.BlockBytes <= (face + 1) * faceBytes,
                    $"Texture {t.Index}, mip {level}, face {face}: tiled address 0x{relative:X} is outside its {faceBytes}-byte allocation.");
                int source = checked(t.PayloadOffset + (int)relative), dest = (y * bw + x) * t.BlockBytes;
                int swap = t.FormatCode == 9 ? 4 : 2;
                for (int k = 0; k < t.BlockBytes; k++)
                    linear[dest + k] = file.Bytes[source + (k / swap) * swap + swap - 1 - k % swap];
            }
            writer.Write(linear);
            if (level < tail) storage += checked(pitch * Align32(bh) * t.BlockBytes);
        }
        }
        return stream.ToArray();
    }

    public static ExportResult Export(string path, string? outputRoot)
    {
        path = Path.GetFullPath(path);
        Require(new FileInfo(path).Length <= MaxFileBytes, "Input exceeds the 512 MiB limit.");
        byte[] bytes = File.ReadAllBytes(path);
        return ExportBytes(path, bytes, outputRoot ?? Path.GetDirectoryName(path)!);
    }

    static ExportResult ExportBytes(string path, byte[] bytes, string outputRoot)
    {
        var parsed = ParseInput(bytes, Path.GetExtension(path));
        // Validate and convert every resource before creating any output folder.
        var converted = parsed.Textures.Select(t => (Texture: t, Dds: ConvertTexture(parsed, t))).ToArray();
        string root = Path.GetFullPath(outputRoot);
        Directory.CreateDirectory(root);
        string stem = Path.GetFileNameWithoutExtension(path);
        string target = Path.Combine(root, stem + "_DDS");
        for (int suffix = 2; Directory.Exists(target) || File.Exists(target); suffix++)
            target = Path.Combine(root, stem + "_DDS_" + suffix);
        string stage = Path.Combine(root, ".lij1_partial_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(stage);
        var outputs = new List<object>();
        foreach (var (t, dds) in converted)
        {
            string name = $"{stem}_{t.Index:00}_{t.Width}x{t.Height}_{t.FourCc}{(t.RawOnly ? ".x360.bin" : ".dds")}";
            File.WriteAllBytes(Path.Combine(stage, name), dds);
            outputs.Add(new { file = name, texture = t, outputBytes = dds.Length,
                ddsBytes = t.RawOnly ? (int?)null : dds.Length,
                sha256 = Convert.ToHexString(SHA256.HashData(dds)).ToLowerInvariant() });
        }
        var manifest = new { tool = "LIJ1 Xbox 360 Prototype Texture Extractor", version = Version,
            source = Path.GetFileName(path), sourceBytes = bytes.Length,
            sourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            conversion = parsed.Textures.Count == 0 ? "No texture payload present"
                : parsed.Textures.All(t => t.FormatCode == -1) ? "Existing DDS preserved byte for byte; no Xbox conversion"
                : "Xbox 360 untile and format-specific endian swap; original blocks/values and exported mip levels, no recompression",
            warnings = parsed.Warnings, outputs };
        File.WriteAllText(Path.Combine(stage, "Extraction.json"), JsonSerializer.Serialize(manifest,
            new JsonSerializerOptions { WriteIndented = true }));
        Directory.Move(stage, target);
        return new(path, target, converted.Count(x => !x.Texture.RawOnly), parsed.Warnings);
    }

    public static IReadOnlyList<string> ExpandInputs(IEnumerable<string> inputs, Action<string>? warning = null)
    {
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        void Visit(string directory)
        {
            try
            {
                foreach (string p in Directory.EnumerateFiles(directory))
                    if (InputExtensions.Contains(Path.GetExtension(p), StringComparer.OrdinalIgnoreCase)) paths.Add(Path.GetFullPath(p));
                foreach (string p in Directory.EnumerateDirectories(directory))
                    if ((File.GetAttributes(p) & FileAttributes.ReparsePoint) == 0 && !Path.GetFileName(p).StartsWith(".lij1_partial_", StringComparison.OrdinalIgnoreCase)
                        && !File.Exists(Path.Combine(p, "Extraction.json")) && !File.Exists(Path.Combine(p, "BatchExtraction.json"))) Visit(p);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { warning?.Invoke($"Cannot scan {directory}: {ex.Message}"); }
        }
        foreach (string input in inputs)
        {
            if (Directory.Exists(input)) Visit(input);
            else paths.Add(Path.GetFullPath(input));
        }
        return paths.OrderBy(p => p, StringComparer.OrdinalIgnoreCase).ToArray();
    }
}
