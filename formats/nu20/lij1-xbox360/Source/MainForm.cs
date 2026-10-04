namespace Lij1Textures;

public sealed class MainForm : Form
{
    readonly TextBox output = new() { Dock = DockStyle.Fill, PlaceholderText = "Default: a new <filename>_DDS folder beside each input" };
    readonly TextBox log = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false };
    readonly Button files = new() { Text = "Choose GHG / GSC files", AutoSize = true };
    readonly Button folder = new() { Text = "Choose a folder", AutoSize = true };
    readonly Label status = new() { Text = "Ready. Drop files or a folder into this window.", Dock = DockStyle.Fill, AutoSize = true };
    bool busy;

    public MainForm(IEnumerable<string> initialInputs, string? initialOutput)
    {
        Text = "LIJ1 Xbox 360 Prototype Texture Extractor " + Extractor.Version;
        Size = new(840, 540); MinimumSize = new(640, 400);
        StartPosition = FormStartPosition.CenterScreen; AllowDrop = true;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new(18), ColumnCount = 1, RowCount = 5 };
        layout.RowStyles.Add(new(SizeType.Absolute, 70));
        layout.RowStyles.Add(new(SizeType.Absolute, 44));
        layout.RowStyles.Add(new(SizeType.Absolute, 44));
        layout.RowStyles.Add(new(SizeType.Percent, 100));
        layout.RowStyles.Add(new(SizeType.Absolute, 30));
        layout.Controls.Add(new Label { Dock = DockStyle.Fill, Text = "Drop prototype .GHG / .GSC files here, or onto the EXE.\nExports original DXT1 / DXT5 textures and mipmaps to DDS. Source files stay unchanged.", AutoSize = true }, 0, 0);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill };
        buttons.Controls.Add(files); buttons.Controls.Add(folder);
        layout.Controls.Add(buttons, 0, 1);
        var outputRow = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3 };
        outputRow.ColumnStyles.Add(new(SizeType.Absolute, 90)); outputRow.ColumnStyles.Add(new(SizeType.Percent, 100)); outputRow.ColumnStyles.Add(new(SizeType.Absolute, 90));
        outputRow.Controls.Add(new Label { Text = "Output folder:", AutoSize = true }, 0, 0);
        outputRow.Controls.Add(output, 1, 0);
        var browse = new Button { Text = "Browse...", Dock = DockStyle.Fill }; outputRow.Controls.Add(browse, 2, 0);
        layout.Controls.Add(outputRow, 0, 2); layout.Controls.Add(log, 0, 3); layout.Controls.Add(status, 0, 4);
        Controls.Add(layout);
        output.Text = initialOutput ?? "";
        files.Click += async (_, _) =>
        {
            using var dialog = new OpenFileDialog { Filter = "Prototype GHG/GSC|*.ghg;*.gsc|All files|*.*", Multiselect = true };
            if (dialog.ShowDialog(this) == DialogResult.OK) await ProcessInputs(dialog.FileNames);
        };
        folder.Click += async (_, _) =>
        {
            using var dialog = new FolderBrowserDialog { Description = "Select a folder to scan for GHG/GSC files (including subfolders)." };
            if (dialog.ShowDialog(this) == DialogResult.OK) await ProcessInputs(new[] { dialog.SelectedPath });
        };
        browse.Click += (_, _) =>
        {
            using var dialog = new FolderBrowserDialog { Description = "Choose a destination for the new DDS folders." };
            if (dialog.ShowDialog(this) == DialogResult.OK) output.Text = dialog.SelectedPath;
        };
        RegisterDrop(this);
        Shown += async (_, _) => { if (initialInputs.Any()) await ProcessInputs(initialInputs); };
        FormClosing += (_, e) => { if (busy) { e.Cancel = true; Append("An extraction is running. Please let it finish before closing."); } };
    }

    void RegisterDrop(Control control)
    {
        control.AllowDrop = true;
        control.DragEnter += (_, e) => e.Effect = !busy && e.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        control.DragDrop += async (_, e) =>
        {
            if (e.Data?.GetData(DataFormats.FileDrop) is string[] paths) await ProcessInputs(paths);
        };
        foreach (Control child in control.Controls) RegisterDrop(child);
    }

    void Append(string message)
    {
        if (InvokeRequired) { BeginInvoke((Action)(() => Append(message))); return; }
        log.AppendText(message + Environment.NewLine);
    }

    async Task ProcessInputs(IEnumerable<string> inputs)
    {
        if (busy) return;
        busy = true; files.Enabled = folder.Enabled = output.Enabled = false;
        string? destination = string.IsNullOrWhiteSpace(output.Text) ? null : output.Text.Trim();
        status.Text = "Extracting...";
        int success = 0, errors = 0;
        try
        {
            await Task.Run(() =>
            {
                var paths = Extractor.ExpandInputs(inputs, message => { Append(message); errors++; });
                if (paths.Count == 0) Append("No GHG/GSC files found in the supplied folder.");
                foreach (string p in paths)
                {
                    try
                    {
                        var result = Extractor.Export(p, destination);
                        foreach (string warning in result.Warnings) Append($"WARNING: {Path.GetFileName(p)} — {warning}");
                        Append($"OK: {Path.GetFileName(p)} — {result.TextureCount} texture(s)\r\n    {result.OutputDirectory}");
                        success++;
                    }
                    catch (Exception ex) { Append($"ERROR: {Path.GetFileName(p)} — {ex.Message}"); errors++; }
                }
            });
        }
        catch (Exception ex) { Append("ERROR: " + ex.Message); errors++; }
        finally
        {
            busy = false; files.Enabled = folder.Enabled = output.Enabled = true;
            status.Text = $"Finished: {success} file(s) exported, {errors} error(s). You can drop more files.";
        }
    }
}
