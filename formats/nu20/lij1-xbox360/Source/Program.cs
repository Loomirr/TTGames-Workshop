using System.Runtime.InteropServices;

namespace Lij1Textures;

internal static class Program
{
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AttachConsole(uint processId);

    [STAThread]
    static int Main(string[] args)
    {
        bool cli = args.Contains("--cli");
        string? output = null;
        var inputs = new List<string>();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--cli") continue;
            if (args[i] == "--out")
            {
                if (++i >= args.Length) return 2;
                output = args[i];
            }
            else inputs.Add(args[i]);
        }
        if (cli)
        {
            AttachConsole(unchecked((uint)-1));
            if (inputs.Count == 0)
            {
                Console.WriteLine("Usage: LIJ1_360_Texture_Extractor.exe --cli [--out folder] file-or-folder [...]");
                return 2;
            }
            bool failed = false;
            var paths = Extractor.ExpandInputs(inputs, message => { Console.WriteLine("ERROR: " + message); failed = true; });
            if (paths.Count == 0) { Console.WriteLine("No GHG/GSC inputs found."); return 1; }
            foreach (string p in paths)
            {
                try
                {
                    var result = Extractor.Export(p, output);
                    foreach (string warning in result.Warnings) Console.WriteLine($"WARNING: {p}: {warning}");
                    Console.WriteLine($"OK: {result.TextureCount} texture(s) -> {result.OutputDirectory}");
                }
                catch (Exception ex) { Console.WriteLine($"ERROR: {p}: {ex.Message}"); failed = true; }
            }
            return failed ? 1 : 0;
        }
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm(inputs, output));
        return 0;
    }
}
