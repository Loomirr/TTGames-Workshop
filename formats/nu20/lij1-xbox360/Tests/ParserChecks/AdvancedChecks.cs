using System.Buffers.Binary;
using System.Text;
using Lij1Textures;

static class AdvancedChecks
{
    static void Put(byte[] b, int at, uint value) => BinaryPrimitives.WriteUInt32BigEndian(b.AsSpan(at, 4), value);
    static void Little(byte[] b, int at, uint value) => BinaryPrimitives.WriteUInt32LittleEndian(b.AsSpan(at, 4), value);
    static uint Read(byte[] b, int at) => BinaryPrimitives.ReadUInt32LittleEndian(b.AsSpan(at, 4));
    static void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
    static byte[] Resource(int format, int width, int height, int mips, int bytes, bool cube = false)
    {
        byte[] b = new byte[4096 + bytes]; Encoding.ASCII.GetBytes("02UN").CopyTo(b, 0);
        Encoding.ASCII.GetBytes("0TST").CopyTo(b, 16); Put(b, 20, (uint)b.Length - 16);
        const int d = 24;
        Put(b, d, (uint)width); Put(b, d + 4, (uint)height);
        Put(b, d + 44, cube ? 0x10000000u : 0x08000000u); Put(b, d + 52, cube ? 1u : 0u);
        Put(b, d + 56, (uint)format); Put(b, d + 60, 4096 - d - 60);
        Put(b, d + 64, (uint)mips); Put(b, d + 68, (uint)bytes); Put(b, d + 80, 3); Put(b, d + 84, 1);
        if (cube) Put(b, d + 944, 0x10000000);
        return b;
    }
    public static int Run()
    {
        int checks = 0;
        void Reject(byte[] b, string extension = ".ghg")
        {
            try { Extractor.ParseInput(b, extension); }
            catch (InvalidDataException) { checks++; return; }
            catch (OverflowException) { checks++; return; }
            throw new Exception("Accepted a corrupt advanced fixture.");
        }
        var cube = Resource(1, 128, 128, 1, 49152, true);
        for (int face = 0; face < 6; face++) { cube[4096 + face * 8192] = (byte)face; cube[4097 + face * 8192] = (byte)(100 + face); }
        var parsed = Extractor.Parse(cube); var dds = Extractor.ConvertTexture(parsed, parsed.Textures[0]);
        Check(parsed.Textures[0].Faces == 6 && Read(dds, 108) == 0x1008 && Read(dds, 112) == 0xfe00 && dds.Length == 128 + 6 * 8192, "Invalid DDS cube header.");
        for (int face = 0; face < 6; face++) Check(dds[128 + face * 8192] == 100 + face && dds[129 + face * 8192] == face, "Cube face ordering changed.");
        checks++;
        var bad = (byte[])cube.Clone(); Put(bad, 24 + 944, 0); Reject(bad);
        bad = (byte[])cube.Clone(); Put(bad, 24 + 180, 1); Reject(bad);
        bad = (byte[])cube.Clone(); Put(bad, 24 + 52, 0); Reject(bad);
        bad = (byte[])cube.Clone(); Put(bad, 24 + 4, 64); Reject(bad);
        var bc5 = Resource(4, 32, 32, 1, 16384); bc5[4096] = 11; bc5[4097] = 22;
        parsed = Extractor.Parse(bc5); dds = Extractor.ConvertTexture(parsed, parsed.Textures[0]);
        Check(Encoding.ASCII.GetString(dds, 84, 4) == "DX10" && Read(dds, 128) == 83 && Read(dds, 132) == 3 && dds.Length == 148 + 1024 && dds[148] == 22, "BC5 header/data incorrect."); checks++;
        var floats = Resource(9, 32, 32, 1, 16384);
        new byte[] { 0x3f, 0x80, 0, 0, 0xc0, 0, 0, 0 }.CopyTo(floats, 4096);
        parsed = Extractor.Parse(floats); dds = Extractor.ConvertTexture(parsed, parsed.Textures[0]);
        Check(Read(dds, 128) == 2 && Read(dds, 20) == 512 && Read(dds, 8) == 0x100f && Read(dds, 148) == 0x3f800000 && Read(dds, 152) == 0xc0000000, "Float endian swap or pitch incorrect."); checks++;
        var small = Resource(1, 8, 8, 4, 8192); small[4096 + 0x100] = 17; small[4096 + 0x101] = 23;
        parsed = Extractor.Parse(small); dds = Extractor.ConvertTexture(parsed, parsed.Textures[0]);
        Check(dds.Length == 184 && dds[128] == 23 && dds[129] == 17, "Small packed base level was not addressed at (16,0) pixels."); checks++;
        var shortTexture = Resource(1, 128, 64, 1, 4096);
        parsed = Extractor.Parse(shortTexture); Check(parsed.Textures[0].RawOnly && parsed.Warnings.Count == 1 && Extractor.ConvertTexture(parsed, parsed.Textures[0]).Length == 4096, "Undersized tiled resource was fabricated as DDS."); checks++;
        byte[] empty = new byte[32]; Encoding.ASCII.GetBytes("02UN").CopyTo(empty, 0); Encoding.ASCII.GetBytes("0TST").CopyTo(empty, 16); Put(empty, 20, 16);
        Check(Extractor.Parse(empty).Textures.Count == 0, "Empty texture chunk was rejected."); checks++;
        var tex = new byte[small.Length + 24]; small.CopyTo(tex, 0);
        Array.Clear(tex, 0, 4096); Put(tex, 0, (uint)tex.Length - 24);
        small.AsSpan(24, 180).CopyTo(tex.AsSpan(4)); Put(tex, 48, 0x20000000); Put(tex, 64, 4096 - 64);
        int end = tex.Length - 24; Put(tex, end, 5);
        int[] targets = [0x20, 0x2c, 0x34, 0x40, 0x50];
        for (int j = 0; j < 5; j++) { int at = end + 4 + j * 4; Put(tex, at, unchecked((uint)(targets[j] - at))); }
        parsed = Extractor.ParseInput(tex, ".tex");
        Check(Extractor.ConvertTexture(parsed, parsed.Textures[0]).SequenceEqual(dds), "Standalone descriptor changed small texture output."); checks++;
        bad = (byte[])tex.Clone(); Put(bad, end + 4, uint.MaxValue); Reject(bad, ".tex");
        bad = (byte[])tex.Clone(); Put(bad, 64, uint.MaxValue); Reject(bad, ".tex");
        bad = (byte[])tex.Clone(); Put(bad, end, 4); Reject(bad, ".tex");
        Reject(tex[..^1], ".tex");
        bad = (byte[])dds.Clone(); Little(bad, 112, 0xfe00); Reject(bad, ".dds");
        Check(Extractor.ConvertTexture(Extractor.ParseInput(dds, ".dds"), Extractor.ParseInput(dds, ".dds").Textures[0]).SequenceEqual(dds), "Existing DDS was rewritten."); checks++;

        var compact = new byte[4096 + 32768 + 8]; int compactEnd = compact.Length - 8;
        Put(compact, 0, (uint)compactEnd); Put(compact, 4, 32); Put(compact, 8, 32);
        Put(compact, 32, 4096 - 32); Put(compact, 36, 32768); Put(compact, 40, 0x1a22aba6);
        Put(compact, compactEnd, 1); Put(compact, compactEnd + 4, unchecked((uint)(32 - compactEnd - 4)));
        parsed = Extractor.ParseInput(compact, ".tex");
        Check(parsed.Textures[0].MipCount == 1 && parsed.Warnings.Count == 1
            && Extractor.ConvertTexture(parsed, parsed.Textures[0]).Length == 148 + 16384, "Invented compact-object mip levels."); checks++;
        bad = (byte[])compact.Clone(); Put(bad, 40, 0x1a22aba7); Reject(bad, ".tex");

        var older = new byte[0x5018]; Encoding.ASCII.GetBytes("02UN").CopyTo(older, 0);
        Encoding.ASCII.GetBytes("DAEH").CopyTo(older, 16); Put(older, 20, 16);
        Encoding.ASCII.GetBytes("LBTN").CopyTo(older, 32); Put(older, 36, 0x41);
        Encoding.ASCII.GetBytes("FERT").CopyTo(older, 0x70); Put(older, 0x74, 12);
        Encoding.ASCII.GetBytes("0TST").CopyTo(older, 0x80); Put(older, 0x84, 8 + 360 + 16384);
        for (int j = 0; j < 2; j++)
        {
            int d = 0x88 + j * 180, pointer = 4096 + j * 8192;
            Little(older, d, 128); Little(older, d + 4, 128); Little(older, d + 56, 0x1a200152);
            Little(older, d + 64, j == 0 ? 0u : 1u); Little(older, d + 68, j == 0 ? 0u : 8192u);
            Put(older, d + 124, 0x1a200152); Put(older, d + 128, 0x00800080); Put(older, d + 136, 0x1a200152);
            Put(older, d + 140, (uint)(pointer - d - 140)); Put(older, d + 144, j == 0 ? 0u : 1u); Put(older, d + 148, j == 0 ? 0u : 8192u);
        }
        Encoding.ASCII.GetBytes("DXAT").CopyTo(older, 0x5000); Put(older, 0x5004, 24);
        parsed = Extractor.Parse(older);
        Check(parsed.Textures[0].MipCount == 1 && !parsed.Textures[0].PackedMips && parsed.Textures[0].PayloadBytes == 8192 && parsed.Warnings.Count == 2, "Missing legacy mip metadata was guessed."); checks++;
        bad = (byte[])older.Clone(); Little(bad, 0x88, 8192); Little(bad, 0x88 + 4, 8192); Put(bad, 0x88 + 128, 0x20002000); Reject(bad);
        return checks;
    }
}
