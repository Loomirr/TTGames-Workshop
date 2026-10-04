using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Lij1Textures;

public sealed record TextureEntry(int Index, int DescriptorOffset, int Width, int Height,
    string Identifier, int FormatCode, string FourCc, int BlockBytes, int MipCount,
    int PayloadOffset, int PayloadBytes);
public sealed record ParsedFile(byte[] Bytes, IReadOnlyList<TextureEntry> Textures);
public sealed record ExportResult(string Source, string OutputDirectory, int TextureCount);

public static class Extractor
{
    public const int MaxFileBytes = 512 * 1024 * 1024;
    const int DescriptorBytes = 180;
    static uint U32(byte[] b, int o) => BinaryPrimitives.ReadUInt32BigEndian(b.AsSpan(o, 4));
    static int I32(byte[] b, int o) => BinaryPrimitives.ReadInt32BigEndian(b.AsSpan(o, 4));
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
            Require(IsPowerOfTwo(width) && IsPowerOfTwo(height) && width >= 32 && height >= 32 && width <= 8192 && height <= 8192,
                $"Unsupported dimensions {width}x{height}. This version supports power-of-two textures from 32 through 8192 pixels.");
            Require(U32(b, cursor + 44) == 0x08000000 && U32(b, cursor + 80) == 3 && U32(b, cursor + 84) == 1,
                $"Unrecognized resource/layout flags in texture {textures.Count}. Refusing to guess a different layout.");
            foreach (var (start, count) in new[] { (24, 20), (48, 8), (72, 8), (88, 92) })
                Require(b.AsSpan(cursor + start, count).IndexOfAnyExcept((byte)0) < 0,
                    $"Unknown descriptor fields in texture {textures.Count}; a new sample is needed.");
            int format = checked((int)U32(b, cursor + 56));
            Require(format is 1 or 6, $"Unsupported texture format code {format} at 0x{cursor + 56:X}. Supported codes: 1 (DXT1), 6 (DXT5).");
            long payloadLong = (long)cursor + 60 + I32(b, cursor + 60);
            int mips = checked((int)U32(b, cursor + 64)), allocated = checked((int)U32(b, cursor + 68));
            Require(mips >= 1 && mips <= Log2(Math.Max(width, height)) + 1, "Invalid mip count.");
            Require(payloadLong >= cursor + DescriptorBytes && payloadLong <= end && (payloadLong & 4095) == 0,
                "Invalid relative payload pointer or alignment.");
            int payload = (int)payloadLong;
            Require(allocated > 0 && allocated <= end - payload, "Texture payload runs outside TST0.");
            int blockBytes = format == 1 ? 8 : 16;
            Require(ExpectedAllocation(width, height, blockBytes, mips) == allocated,
                $"Texture {textures.Count} has an unrecognized mip allocation ({allocated} bytes). Refusing to produce a corrupt DDS.");
            firstPayload = Math.Min(firstPayload, payload);
            textures.Add(new(textures.Count, cursor, width, height,
                Convert.ToHexString(b.AsSpan(cursor + 8, 16)).ToLowerInvariant(),
                format, format == 1 ? "DXT1" : "DXT5", blockBytes, mips, payload, allocated));
            cursor += DescriptorBytes;
        }
        Require(textures.Count > 0 && cursor <= firstPayload, "TST0 contains no supported textures.");
        Require(b.AsSpan(cursor, firstPayload - cursor).IndexOfAnyExcept((byte)0) < 0,
            "Texture descriptor padding contains unknown data.");
        int payloadEnd = firstPayload;
        foreach (var t in textures.OrderBy(t => t.PayloadOffset))
        {
            Require(t.PayloadOffset == payloadEnd, "Texture payloads overlap or have an unrecognized gap.");
            payloadEnd = checked(t.PayloadOffset + t.PayloadBytes);
        }
        Require(payloadEnd == end, "Unrecognized trailing data inside TST0.");
        return new(b, textures);
    }

    static long ExpectedAllocation(int w, int h, int bytes, int mips)
    {
        int tail = Math.Max(0, Math.Min(Log2(w), Log2(h)) - 4);
        long size = 0;
        for (int level = 0; level < mips; level++)
        {
            size += (long)Align32(Blocks(Math.Max(1, w >> level))) * Align32(Blocks(Math.Max(1, h >> level))) * bytes;
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
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream, Encoding.ASCII, true);
        writer.Write("DDS "u8);
        writer.Write(124u);
        writer.Write(t.MipCount > 1 ? 0xa1007u : 0x81007u);
        writer.Write(t.Height); writer.Write(t.Width);
        writer.Write(Blocks(t.Width) * Blocks(t.Height) * t.BlockBytes);
        writer.Write(0); writer.Write(t.MipCount);
        for (int i = 0; i < 11; i++) writer.Write(0);
        writer.Write(32); writer.Write(4); writer.Write(Encoding.ASCII.GetBytes(t.FourCc));
        for (int i = 0; i < 5; i++) writer.Write(0);
        writer.Write(t.MipCount > 1 ? 0x401008u : 0x1000u);
        for (int i = 0; i < 4; i++) writer.Write(0);
        Require(stream.Length == 128, "Internal DDS header size error.");

        int tail = Math.Max(0, Math.Min(Log2(t.Width), Log2(t.Height)) - 4);
        int storage = 0;
        for (int level = 0; level < t.MipCount; level++)
        {
            int bw = Blocks(Math.Max(1, t.Width >> level)), bh = Blocks(Math.Max(1, t.Height >> level));
            int pitch = Align32(bw), x0 = 0, y0 = 0;
            if (level >= tail)
            {
                pitch = Align32(Blocks(t.Width >> tail));
                int packed = level - tail;
                if (packed < 3)
                {
                    if (t.Width > t.Height) y0 = (16 >> packed) / 4;
                    else x0 = (16 >> packed) / 4;
                }
                else
                {
                    int offset = (Math.Max(t.Width, t.Height) >> tail) >> (packed - 2);
                    if (t.Width > t.Height) x0 = offset / 4;
                    else y0 = offset / 4;
                }
            }
            byte[] linear = new byte[checked(bw * bh * t.BlockBytes)];
            for (int y = 0; y < bh; y++)
            for (int x = 0; x < bw; x++)
            {
                long relative = storage + TiledAddress(x + x0, y + y0, pitch, t.BlockBytes == 8 ? 3 : 4);
                Require(relative >= 0 && relative + t.BlockBytes <= t.PayloadBytes, "Tiled mip address is outside the resource.");
                int source = checked(t.PayloadOffset + (int)relative), dest = (y * bw + x) * t.BlockBytes;
                for (int k = 0; k < t.BlockBytes; k += 2)
                {
                    linear[dest + k] = file.Bytes[source + k + 1];
                    linear[dest + k + 1] = file.Bytes[source + k];
                }
            }
            writer.Write(linear);
            if (level < tail) storage += checked(pitch * Align32(bh) * t.BlockBytes);
        }
        return stream.ToArray();
    }

    public static ExportResult Export(string path, string? outputRoot)
    {
        path = Path.GetFullPath(path);
        Require(new FileInfo(path).Length <= MaxFileBytes, "Input exceeds the 512 MiB limit.");
        byte[] bytes = File.ReadAllBytes(path);
        var parsed = Parse(bytes);
        // Validate and convert every resource before creating any output folder.
        var converted = parsed.Textures.Select(t => (Texture: t, Dds: ConvertTexture(parsed, t))).ToArray();
        string root = outputRoot is null ? Path.GetDirectoryName(path)! : Path.GetFullPath(outputRoot);
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
            string name = $"{stem}_{t.Index:00}_{t.Width}x{t.Height}_{t.FourCc}.dds";
            File.WriteAllBytes(Path.Combine(stage, name), dds);
            outputs.Add(new { file = name, texture = t, ddsBytes = dds.Length,
                sha256 = Convert.ToHexString(SHA256.HashData(dds)).ToLowerInvariant() });
        }
        var manifest = new { tool = "LIJ1 Xbox 360 Prototype Texture Extractor", version = "0.1.0",
            source = Path.GetFileName(path), sourceBytes = bytes.Length,
            sourceSha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            conversion = "Xbox 360 2D untile, 8-in-16 byte swap, original BC1/BC3 blocks and mip chain; no recompression",
            outputs };
        File.WriteAllText(Path.Combine(stage, "Extraction.json"), JsonSerializer.Serialize(manifest,
            new JsonSerializerOptions { WriteIndented = true }));
        Directory.Move(stage, target);
        return new(path, target, converted.Length);
    }

    public static IReadOnlyList<string> ExpandInputs(IEnumerable<string> inputs, Action<string>? warning = null)
    {
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        void Visit(string directory)
        {
            try
            {
                foreach (string p in Directory.EnumerateFiles(directory))
                    if (Path.GetExtension(p).Equals(".ghg", StringComparison.OrdinalIgnoreCase) ||
                        Path.GetExtension(p).Equals(".gsc", StringComparison.OrdinalIgnoreCase)) paths.Add(Path.GetFullPath(p));
                foreach (string p in Directory.EnumerateDirectories(directory))
                    if ((File.GetAttributes(p) & FileAttributes.ReparsePoint) == 0) Visit(p);
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
