using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;
using Lij1Textures;

void Put(byte[] b, int o, uint v) => BinaryPrimitives.WriteUInt32BigEndian(b.AsSpan(o, 4), v);
void Little(byte[] b, int o, uint v) => BinaryPrimitives.WriteUInt32LittleEndian(b.AsSpan(o, 4), v);
void Tag(byte[] b, int o, string v) => System.Text.Encoding.ASCII.GetBytes(v).CopyTo(b, o);
void Check(bool value, string message) { if (!value) throw new Exception(message); }

byte[] Sample(uint layout = 1, int allocation = 8192)
{
    byte[] b = new byte[4096 + allocation];
    Tag(b, 0, "02UN"); Tag(b, 16, "0TST"); Put(b, 20, (uint)(b.Length - 16));
    const int d = 24;
    Put(b, d, 32); Put(b, d + 4, 32); Put(b, d + 44, 0x08000000);
    Put(b, d + 56, 1); Put(b, d + 60, 4096 - d - 60);
    Put(b, d + 64, 1); Put(b, d + 68, (uint)allocation);
    Put(b, d + 80, 3); Put(b, d + 84, layout);
    if (layout == 0)
    {
        Put(b, d + 128, 0x00200020); Put(b, d + 136, 0x1a200152);
        Put(b, d + 140, 4096 - d - 140); Put(b, d + 144, 1); Put(b, d + 148, (uint)allocation);
    }
    // Distinct source bytes allow byte-swap and block-address assertions.
    for (int i = 4096; i < b.Length; i++) b[i] = (byte)(i ^ (i >> 8));
    return b;
}

byte[] Legacy()
{
    byte[] b = new byte[0xd018];
    Tag(b, 0, "02UN"); Tag(b, 0x10, "DAEH"); Put(b, 0x14, 16);
    Tag(b, 0x20, "LBTN"); Put(b, 0x24, 0x41); Put(b, 0x28, 0x35);
    Tag(b, 0x61, "FERT"); Put(b, 0x65, 12); Tag(b, 0x6d, "0TS");
    Tag(b, 0x70, "FERT"); Put(b, 0x74, 12); Tag(b, 0x80, "0TST"); Put(b, 0x84, 0xc0bc);
    const int d = 0x88;
    Little(b, d, 64); Little(b, d + 4, 64); Little(b, d + 56, 0x1a200154);
    Little(b, d + 60, 0x270f0129); Little(b, d + 64, 7); Little(b, d + 68, 0xc000);
    Put(b, d + 124, 0x1a200154); Put(b, d + 128, 0x00400040);
    Put(b, d + 136, 0x1a200154); Put(b, d + 140, 4096 - d - 140);
    Put(b, d + 144, 7); Put(b, d + 148, 0xc000);
    Tag(b, 0xd000, "DXAT"); Put(b, 0xd004, 24);
    return b;
}

int checks = 0;
void Reject(string name, byte[] b, Action<byte[]>? change = null)
{
    change?.Invoke(b);
    try { Extractor.Parse(b); }
    catch (InvalidDataException) { checks++; return; }
    catch (OverflowException) { checks++; return; }
    throw new Exception("Accepted invalid input: " + name);
}

foreach (var (layout, allocation) in new[] { (1u,8192), (1u,4096), (0u,8192), (0u,4096) })
{
    byte[] b = Sample(layout, allocation);
    byte[] original = (byte[])b.Clone();
    var parsed = Extractor.Parse(b);
    var dds = Extractor.ConvertTexture(parsed, parsed.Textures[0]);
    Check(dds.Length == 128 + 512, "Unexpected one-level DDS length.");
    Check(dds[128] == b[4097] && dds[129] == b[4096], "Incorrect pair swap.");
    const int tiled = 0x738; // Independently evaluated Xbox address for block (7,7).
    Check(dds[^8] == b[4096 + tiled + 1], "Incorrect block recovery.");
    Check(b.SequenceEqual(original), "Parse/conversion changed input bytes.");
    Check(parsed.Warnings.Count == 0, "Ordinary layout reported recovery.");
    checks++;
}
var legacy = Extractor.Parse(Legacy());
Check(legacy.Warnings.Count == 1 && legacy.Textures[0].PayloadOffset == 4096
    && legacy.Textures[0].DescriptorProfile == "legacy-mixed-endian-icon", "Missing recovery provenance.");
Check(Extractor.ConvertTexture(legacy, legacy.Textures[0]).Length == 5616, "Wrong legacy mip chain length.");
checks++;

Reject("unsupported flags", Sample(), b => Put(b, 24 + 84, 2));
Reject("unknown resource flag", Sample(), b => Put(b, 24 + 44, 0x10000000));
Reject("unknown format", Sample(), b => Put(b, 24 + 56, 4));
Reject("unknown reserved data", Sample(), b => b[24 + 100] = 1);
Reject("non power of two", Sample(), b => Put(b, 24, 31));
Reject("small dimension", Sample(), b => Put(b, 24, 8));
Reject("invalid mip count", Sample(), b => Put(b, 24 + 64, 20));
Reject("invalid chunk length", Sample(), b => Put(b, 20, uint.MaxValue));
Reject("descriptor padding", Sample(), b => b[0x300] = 1);
Reject("unaligned pointer", Sample(), b => Put(b, 24 + 60, 4097 - 24 - 60));
Reject("out of bounds pointer", Sample(), b => Put(b, 24 + 60, int.MaxValue));
Reject("overrun allocation", Sample(), b => Put(b, 24 + 68, 0x100000));
Reject("unrecognized allocation", Sample(), b => Put(b, 24 + 68, 2048));
Reject("secondary dimensions", Sample(0), b => Put(b, 24 + 128, 0x00400020));
Reject("secondary format", Sample(0), b => Put(b, 24 + 136, 0x1a200154));
Reject("secondary pointer", Sample(0), b => Put(b, 24 + 140, 0));
Reject("secondary mip count", Sample(0), b => Put(b, 24 + 144, 2));
Reject("secondary allocation", Sample(0), b => Put(b, 24 + 148, 4096));
Reject("secondary reserved fields", Sample(0), b => b[24 + 132] = 1);
Reject("unbounded signature scan", Sample(), b => Put(b, 20, 4));
Reject("legacy primary dimensions", Legacy(), b => Little(b, 0x88, 128));
Reject("legacy format", Legacy(), b => Little(b, 0x88 + 56, 0x1a200152));
Reject("legacy chunk size", Legacy(), b => Put(b, 0x84, 0xcf80));
Reject("legacy pointer", Legacy(), b => Put(b, 0x88 + 140, 0));
Reject("legacy duplicate dimensions", Legacy(), b => Put(b, 0x88 + 128, 0x00800040));
Reject("legacy duplicate mip count", Legacy(), b => Put(b, 0x88 + 144, 6));
Reject("legacy missing following chunk", Legacy(), b => Tag(b, 0xd000, "JUNK"));
Reject("legacy following chunk size", Legacy(), b => Put(b, 0xd004, 32));
Reject("legacy truncated allocation", Legacy()[..0xc000]);
Reject("legacy truncated following chunk", Legacy()[..0xd010]);
Reject("truncated ordinary payload", Sample()[..5000]);
Console.WriteLine($"{checks} synthetic parser/converter checks passed.");

if (args.Length == 0) return;
if (args.Length is < 3 or > 4 || args[0] != "--survey" || (args.Length == 4 && args[3] != "--convert"))
    throw new ArgumentException("Usage: [--survey input-folder new-report.json [--convert]]");
string input = Path.GetFullPath(args[1]), report = Path.GetFullPath(args[2]);
Check(!File.Exists(report), "Use a new survey report path.");
var results = new List<object>();
int accepted = 0, rejected = 0, textures = 0, mips = 0;
var options = new EnumerationOptions { RecurseSubdirectories = true, AttributesToSkip = FileAttributes.ReparsePoint };
foreach (string path in Directory.EnumerateFiles(input, "*", options).Order())
{
    if (!new[] { ".ghg", ".gsc" }.Contains(Path.GetExtension(path).ToLowerInvariant())) continue;
    try
    {
        byte[] b = File.ReadAllBytes(path);
        var parsed = Extractor.Parse(b);
        var items = parsed.Textures.Select(t => new {
            texture = t, sha256 = args.Length == 4 ? Convert.ToHexString(
                SHA256.HashData(Extractor.ConvertTexture(parsed, t))).ToLowerInvariant() : null }).ToArray();
        results.Add(new { file = Path.GetRelativePath(input, path), success = true,
            sourceSha256 = Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant(), warnings = parsed.Warnings, outputs = items });
        accepted++; textures += parsed.Textures.Count; mips += parsed.Textures.Sum(t => t.MipCount);
    }
    catch (Exception ex) when (ex is InvalidDataException or OverflowException or IOException)
    {
        results.Add(new { file = Path.GetRelativePath(input, path), success = false, error = ex.Message });
        rejected++;
    }
}
Directory.CreateDirectory(Path.GetDirectoryName(report)!);
File.WriteAllText(report, JsonSerializer.Serialize(new { accepted, rejected, textures, mips, results }, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"Survey: {accepted} accepted, {rejected} rejected, {textures} textures, {mips} mip levels.");
