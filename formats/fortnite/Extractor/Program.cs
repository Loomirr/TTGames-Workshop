// Original Workshop bridge to a separately supplied Unreal reader. No Epic
// account integration, automatic key downloads, telemetry or binary downloads.
using System.Text.Json;
using System.Text.RegularExpressions;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.Compression;
using CUE4Parse.UE4.IO;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Textures;
using CUE4Parse_Conversion.Options;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

if (args.Length < 2 || args[0] is not ("index" or "export") || (args[0] == "export" && args.Length != 3))
    throw new ArgumentException("Usage: Workshop.Fortnite.Extractor index settings.json | export settings.json source-package");
var configPath = Path.GetFullPath(args[1]);
using var configDoc = JsonDocument.Parse(File.ReadAllText(configPath));
var config = configDoc.RootElement;
string Setting(string key) => config.GetProperty(key).GetString() ?? throw new ArgumentException($"Missing {key}");
string InputPath(string key) => Path.GetFullPath(Setting(key), Path.GetDirectoryName(configPath)!);
var game = InputPath("paks");
var output = InputPath("output");
if (output.Equals(game, StringComparison.OrdinalIgnoreCase) || output.StartsWith(game + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
    throw new ArgumentException("Output must be outside the game archives");
var archiveFolder = new DirectoryInfo(game);
if (archiveFolder.Name.Equals("Paks", StringComparison.OrdinalIgnoreCase) && archiveFolder.Parent?.Name == "Content" && archiveFolder.Parent.Parent?.Name == "FortniteGame")
{
    var installRoot = archiveFolder.Parent.Parent.Parent!.FullName;
    if (output.Equals(installRoot, StringComparison.OrdinalIgnoreCase) || output.StartsWith(installRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must be outside the Fortnite installation");
}
// This is a reader API/version gate, not a claim of all Fortnite build support.
if (Setting("engineVersion") != "GAME_UE6_0")
    throw new ArgumentException("Only the reviewed GAME_UE6_0 reader profile has been checked");
Directory.CreateDirectory(output);
Directory.CreateDirectory(Path.Combine(output, "Exports"));
Directory.CreateDirectory(Path.Combine(output, "Models"));
var originalFiles = Directory.GetFiles(game, "*.utoc").Concat(Directory.GetFiles(game, "*.pak"))
    .ToDictionary(p => p, p => (new FileInfo(p).Length, File.GetLastWriteTimeUtc(p)));
if (originalFiles.Count == 0) throw new ArgumentException("No PAK/UTOC archives found");
OodleHelper.Initialize(new OodleDotNet.Oodle(InputPath("oodle")));
using var provider = new DefaultFileProvider(game, SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE6_0), StringComparer.OrdinalIgnoreCase);
if (config.TryGetProperty("chunkHost", out var chunkHost) && chunkHost.ValueKind == JsonValueKind.String)
{
    var host = new Uri(chunkHost.GetString()!);
    if (host.Scheme != "https") throw new ArgumentException("Streamed chunk host must use HTTPS");
    provider.OnDemandOptions = new IoStoreOnDemandOptions { ChunkHostUri = host,
        ChunkCacheDirectory = Directory.CreateDirectory(Path.Combine(output, "StreamCache")), Timeout = TimeSpan.FromSeconds(30) };
}
provider.Initialize();
using var keyDoc = JsonDocument.Parse(File.ReadAllText(InputPath("keyFile")));
var keys = keyDoc.RootElement.GetProperty("keys");
provider.SubmitKey(new FGuid(), new FAesKey(keys.GetProperty("mainKey").GetProperty("key").GetString()!));
foreach (var key in keys.GetProperty("extraKeys").EnumerateArray())
    provider.SubmitKey(new FGuid(key.GetProperty("guid").GetString()!), new FAesKey(key.GetProperty("key").GetString()!));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(InputPath("mappings"));
provider.PostMount();
provider.LoadVirtualPaths();
Console.WriteLine($"Mounted {provider.Files.Count} resources");
var pattern = new Regex(@"/Figure/Figure_(?<code>[^/]+)/(?:(?:Mutable/Dataless/COI_Figure_[^/]+_Dataless)|(?:Bake/FigureBake_[^/]+))\.uasset$", RegexOptions.IgnoreCase);
string VirtualPath(string path)
{
    var index = path.IndexOf("/Content/", StringComparison.OrdinalIgnoreCase);
    if (index < 0) throw new InvalidDataException("Unrecognized exported package path");
    var prefix = path[..index].Split('/').Last();
    return (prefix == "FortniteGame" ? "Game" : prefix) + path[(index+8)..];
}
// Name aliases are user supplied. This inventory never labels a codename as a
// verified human character name when no matching cosmetic metadata is available.
var nameFile = Path.Combine(output, "character-names.json");
var names = File.Exists(nameFile) ? System.Text.Json.JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(nameFile))! : [];
var entries = new List<object>();
var indexedResources = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
foreach (var path in provider.Files.Keys.Order())
{
    var match = pattern.Match(path);
    if (!match.Success) continue;
    var code = match.Groups["code"].Value;
    var basename = Path.GetFileNameWithoutExtension(path);
    var mode = basename.StartsWith("COI_", StringComparison.OrdinalIgnoreCase) ? "recipe" : "baked";
    if (mode == "baked" && !basename.Equals("FigureBake_" + code, StringComparison.OrdinalIgnoreCase)) continue;
    var resource = VirtualPath(path)[..^7];
    if (!indexedResources.Add(resource)) continue;
    entries.Add(new { resource, backend_resource = path, mode, code,
        label = names.GetValueOrDefault(code, code), source = path });
}
var indexData = new { schema = "tt-workshop.lego-fortnite-index.v1", reader = "GAME_UE6_0", entries };
var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
File.WriteAllText(Path.Combine(output, "lego-fortnite-index.json"), System.Text.Json.JsonSerializer.Serialize(indexData, jsonOptions));
if (args[0] == "export")
{
    var requested = provider[args[2]].Path;
    if (!pattern.IsMatch(requested)) throw new ArgumentException("Select an indexed LEGO figure recipe or baked body");
    var figureDir = requested[..requested.IndexOf("/Figure/", StringComparison.OrdinalIgnoreCase)] + "/Figure/Figure_" + pattern.Match(requested).Groups["code"].Value + "/";
    var queue = new Queue<string>();
    queue.Enqueue(requested);
    foreach (var path in provider.Files.Keys.Where(p => p.StartsWith(figureDir, StringComparison.OrdinalIgnoreCase) &&
        p.Contains("/Material/", StringComparison.OrdinalIgnoreCase) && p.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase))) queue.Enqueue(path);
    foreach (var common in new[] { "/FigureCharacter/Figure_Core/SkeletalMesh/SKM_Figure_Preview.uasset",
        "/JunoBase/EditorUtility/LUT_Generator/Variants/T_LUT_Default.uasset" })
        queue.Enqueue(provider[common].Path);
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var results = new List<object>();
    var session = new ExportSession { MaxDegreeOfParallelism = 1 };
    TextureDecoder.UseAssetRipperTextureDecoder = true;
    while (queue.TryDequeue(out var current))
    {
        var path = provider[current].Path;
        if (!seen.Add(path)) continue;
        if (seen.Count > 4096) throw new InvalidDataException("Reference traversal exceeded one-character bound");
        try
        {
            var exports = provider.LoadPackage(path).GetExports().ToArray();
            var destination = Path.GetFullPath(Path.Combine(output, "Exports", path));
            if (!destination.StartsWith(output + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Package path escaped export folder");
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            var metadata = JsonConvert.SerializeObject(exports, Formatting.Indented);
            File.WriteAllText(Path.ChangeExtension(destination, "json"), metadata);
            foreach (var mesh in exports.OfType<USkinnedAsset>()) session.Add(mesh);
            foreach (var token in JToken.Parse(metadata).SelectTokens("$..ObjectPath"))
            {
                var reference = ((string?)token)?.Split('.')[0];
                if (string.IsNullOrEmpty(reference)) continue;
                var name = reference.Split('/').Last();
                if (new[] { "T_", "TA_", "MI_", "M_", "SK_", "SKM_", "FigureBake_" }.Any(prefix => name.StartsWith(prefix)) &&
                    provider.TryGetGameFile(reference + ".uasset", out var file)) queue.Enqueue(file.Path);
            }
            foreach (var texture in exports.OfType<UTexture>())
            {
                // Do not silently choose a small resident mip when high mips
                // live in optional streamed containers.
                var decoded = texture.DecodeMip(0) ?? throw new InvalidDataException("Highest serialized texture mip is unavailable; provide the streamed asset cache/CDN");
                File.WriteAllBytes(Path.Combine(Path.GetDirectoryName(destination)!, texture.Name + ".png"), decoded.Encode(ETextureFormat.Png, false, out _));
                results.Add(new { path, status = "texture", name = texture.Name, width = decoded.Width, height = decoded.Height, mip = 0 });
            }
            results.Add(new { path, status = "exported" });
        }
        catch (Exception error)
        {
            // Store parser errors privately; never print key configuration.
            results.Add(new { path, status = "failed", error = error.GetType().Name, reason = error.GetBaseException().Message });
        }
    }
    var meshResults = await session.RunAsync(Path.Combine(output, "Models"), new ExportOptions(meshFormat: EMeshFormat.Gltf2, exportMaterials: false));
    File.WriteAllText(Path.Combine(output, "last-export.json"), System.Text.Json.JsonSerializer.Serialize(new { resource = requested, packages = results, meshes = meshResults }, jsonOptions));
    Console.WriteLine($"Exported/reported {seen.Count} packages; see last-export.json");
}
foreach (var (path, info) in originalFiles)
    if (info != (new FileInfo(path).Length, File.GetLastWriteTimeUtc(path))) throw new IOException("Game archives changed during extraction; retry on a stable installation");
Console.WriteLine($"Indexed {entries.Count} LEGO figure sources");
