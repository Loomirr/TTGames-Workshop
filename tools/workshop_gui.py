"""Small Tkinter front end for the Workshop's standalone Python tools."""
from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.5'
DEFAULT_TOOL_VERSION = '0.1.1'
TOOL_VERSIONS = {'3DS BTGA to DDS / PNG': '0.1.2', 'Face targets: decode': '0.1.3',
                 'Face targets: write edited copy': '0.1.3', 'DCSV archive index': '0.1.5',
                 'TFA archive index': '0.1.4', 'CU3 dependency report': '0.1.4'}
# Fields: label, kind, command-line flag (None means positional), default.
TOOLS = {
    '3DS BTGA to DDS / PNG': (
        'formats/btga/3ds/btga_to_dds.py',
        'Universe in Peril: already-decompressed BTGA only. Requires Pillow. Preserves original pixels and stored mips.',
        [('BTGA file', 'file', None, ''), ('New output folder', 'outdir', None, '')]),
    'LMSH1 AN4 decode': (
        'formats/an4/lmsh1/decode_an4.py',
        'Observed LMSH1 AN4 layouts and HGOLv10 63-joint rig only. Review decode-manifest.json for skipped or unsupported clips.',
        [('AN4 file or folder', 'source', None, ''), ('Skeleton GHG', 'file', None, ''),
         ('New output folder', 'outdir', None, ''), ('Exact actor name', 'text', '--actor', ''),
         ('Clip index', 'integer', '--clip-index', '0')]),
    'LMSH1 decoded animation to BVH': (
        'formats/an4/lmsh1/export_bvh.py',
        'Experimental transform preview, not a verified animation conversion. Select the decoder output containing skeleton.json and decode-manifest.json.',
        [('Decoded folder', 'dir', None, ''), ('New output folder', 'outdir', None, ''),
         ('FPS assumption', 'fps', '--fps', '30')]),
    'CU3 dependency report': (
        'formats/cu3/scripts/check_dependencies.py',
        'LB3 / LMSH1 only. Checks an extracted CU3 against installed or extracted game assets. Companion cache must be outside the game folder.',
        [('CU3 file', 'file', None, ''), ('Game / extracted assets folder', 'dir', '--assets', ''),
         ('Game', 'game', '--game', 'LB3'), ('Cache folder', 'cache', '--cache', ''),
         ('New report JSON', 'outfile', '--report', '')]),
    'Face targets: decode': (
        'formats/cu3/scripts/decode_face_targets.py',
        'Reads supported MESH 169/170/175 face GHGs directly. No extraction log is needed. Produces target JSON; this is not a visual face editor.',
        [('Original GHG', 'file', None, ''),
         ('New target JSON', 'outfile', '--output', '')]),
    'Face targets: write edited copy': (
        'formats/cu3/scripts/write_face_targets.py',
        'Advanced: observed MESH 169/170/175 target offsets only. Requires verified edited-target JSON, preserving topology and source hash. Writes a separate GHG; in-game validation still required.',
        [('Original GHG', 'file', None, ''), ('Edited target JSON', 'file', '--edited', ''),
         ('New GHG copy', 'outfile', '--output', '')]),
    'TFA archive index': (
        'formats/cu3/scripts/archive_index_cc8.py',
        'The Force Awakens CC8 DAT / HDR index only. Lists file paths; does not extract models or complete scenes.',
        [('DAT / HDR file', 'file', None, ''), ('New index JSON', 'outfile', None, '')]),
    'DCSV archive index': (
        'formats/cu3/scripts/archive_index_cc4.py',
        'DC Super-Villains CC4 archive index only. Lists file paths; does not extract models or complete scenes.',
        [('Archive file', 'file', None, ''), ('New index JSON', 'outfile', None, '')]),
}


def python_executable():
    executable = Path(sys.executable)
    if executable.name.lower() == 'pythonw.exe':
        executable = executable.with_name('python.exe')
    return str(executable)


def build_command(name, values):
    """Validate all inputs before spawning. Never use a shell or overwrite outputs."""
    script, _, fields = TOOLS[name]
    if len(values) != len(fields):
        raise ValueError('Missing form fields')
    command = [python_executable(), '-u', str(ROOT / script)]
    inputs, outputs, caches = [], [], []
    for (label, kind, flag, _), value in zip(fields, values):
        value = value.strip()
        if not value:
            raise ValueError(f'{label} is required')
        if kind in ('file', 'dir', 'source', 'outdir', 'outfile', 'cache'):
            path = Path(value).expanduser().resolve()
            value = str(path)
            if kind == 'file' and not path.is_file():
                raise ValueError(f'{label}: choose an existing file')
            if kind == 'dir' and not path.is_dir():
                raise ValueError(f'{label}: choose an existing folder')
            if kind == 'source' and not (path.is_file() or path.is_dir()):
                raise ValueError(f'{label}: choose an existing file or folder')
            if kind.startswith('out'):
                if path.exists():
                    raise ValueError(f'{label}: choose a NEW name; existing outputs are protected')
                if not path.parent.is_dir():
                    raise ValueError(f'{label}: parent folder must already exist')
                outputs.append(path)
            elif kind == 'cache':
                if path.exists() and not path.is_dir():
                    raise ValueError('Cache must be a folder')
                caches.append(path)
            else:
                inputs.append(path)
        elif kind == 'integer':
            if not value.isdecimal():
                raise ValueError('Clip index must be a nonnegative integer')
        elif kind == 'fps':
            if not 0 < float(value) < 1000:
                raise ValueError('FPS must be between 0 and 1000')
        elif kind == 'game' and value not in ('LB3', 'LMSH1'):
            raise ValueError('Choose LB3 or LMSH1')
        if flag:
            command.append(flag)
        command.append(value)
    for target in outputs + caches:
        for source in inputs:
            if target == source or (source.is_dir() and target.is_relative_to(source)):
                raise ValueError('Put outputs and cache outside the input / game folder')
    return command, outputs


def run_command(command, events):
    """Only sends queue messages; never touches Tk from the worker thread."""
    try:
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              text=True, encoding='utf-8', errors='replace',
                              env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, **options) as process:
            for line in process.stdout:
                events.put(('log', line))
            events.put(('done', process.wait()))
    except Exception as error:
        events.put(('log', f'{type(error).__name__}: {error}\n'))
        events.put(('done', -1))


class Workshop:
    def __init__(self, window, tool=None):
        if tool is not None and tool not in TOOLS:
            raise ValueError(f'Unknown tool: {tool}')
        self.tool = tool
        self.window = window
        self.events = queue.Queue()
        self.running = False
        self.outputs = []
        self.saved = {}
        self.current = None
        version=TOOL_VERSIONS.get(tool,DEFAULT_TOOL_VERSION) if tool else VERSION
        window.title(f'{tool or "TTGames Workshop — Standalone Tools"} {version}')
        window.geometry('880x700')
        window.minsize(700, 600)
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='TTGames Workshop', font=('', 16, 'bold')).pack(anchor='w')
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=8)
        if tool is None:
            ttk.Button(bar, text='CU3 name editor', command=self.name_editor).pack(side='left')
        ttk.Button(bar, text='Help', command=self.help).pack(side='left', padx=8)
        self.choice = ttk.Combobox(frame, values=[tool] if tool else list(TOOLS), state='readonly')
        if tool is None:
            self.choice.pack(fill='x')
        else:
            ttk.Label(frame, text=tool, font=('', 12, 'bold')).pack(anchor='w')
        self.choice.bind('<<ComboboxSelected>>', self.select)
        self.description = ttk.Label(frame, wraplength=810)
        self.description.pack(fill='x', pady=10)
        self.form = ttk.Frame(frame)
        self.form.pack(fill='x')
        self.form.columnconfigure(1, weight=1)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=12)
        self.run_button = ttk.Button(buttons, text='Run tool', command=self.run)
        self.run_button.pack(side='left')
        self.open_button = ttk.Button(buttons, text='Open output folder', command=self.open_output, state='disabled')
        self.open_button.pack(side='left', padx=8)
        self.status = ttk.Label(buttons, text='Ready')
        self.status.pack(side='left', padx=8)
        self.log = ScrolledText(frame, height=12, wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True)
        self.choice.current(0)
        self.select()
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(100, self.poll)

    def select(self, _event=None):
        if self.current:
            self.saved[self.current] = [v.get() for v in self.values]
        self.current = self.choice.get()
        _, description, fields = TOOLS[self.current]
        self.description.config(text=description)
        for child in self.form.winfo_children():
            child.destroy()
        self.values = []
        saved = self.saved.get(self.current, [f[3] for f in fields])
        for row, ((label, kind, _, _), value) in enumerate(zip(fields, saved)):
            ttk.Label(self.form, text=label).grid(row=row, column=0, sticky='w', pady=5, padx=(0, 10))
            variable = tk.StringVar(value=value)
            self.values.append(variable)
            widget = (ttk.Combobox(self.form, textvariable=variable, values=('LB3', 'LMSH1'), state='readonly')
                      if kind == 'game' else ttk.Entry(self.form, textvariable=variable))
            widget.grid(row=row, column=1, sticky='ew', pady=5)
            if kind in ('file', 'dir', 'source', 'outdir', 'outfile', 'cache'):
                ttk.Button(self.form, text='Browse…', command=lambda v=variable, k=kind: self.browse(v, k)).grid(row=row, column=2, padx=5)
            if kind == 'source':
                ttk.Button(self.form, text='Folder…', command=lambda v=variable: self.browse(v, 'dir')).grid(row=row, column=3)

    def browse(self, variable, kind):
        if kind in ('dir', 'cache'):
            path = filedialog.askdirectory(parent=self.window, mustexist=kind == 'dir')
        elif kind in ('outdir', 'outfile'):
            path = filedialog.asksaveasfilename(parent=self.window, title='Choose a NEW ' + ('folder name' if kind == 'outdir' else 'output filename'))
        else:
            path = filedialog.askopenfilename(parent=self.window)
        if path:
            variable.set(path)

    def append(self, text):
        self.log.config(state='normal')
        self.log.insert('end', text)
        # Bound long decoder logs while retaining the most recent messages.
        if int(self.log.index('end-1c').split('.')[0]) > 2500:
            self.log.delete('1.0', '501.0')
        self.log.see('end')
        self.log.config(state='disabled')

    def run(self):
        if self.running:
            return
        try:
            command, self.outputs = build_command(self.current, [v.get() for v in self.values])
        except (ValueError, OSError) as error:
            messagebox.showerror('Check inputs', str(error), parent=self.window)
            return
        self.running = True
        self.run_button.config(state='disabled')
        self.choice.config(state='disabled')
        self.open_button.config(state='disabled')
        self.status.config(text='Running…')
        self.append(f'\n--- {self.current} ---\n')
        threading.Thread(target=run_command, args=(command, self.events), daemon=True).start()

    def poll(self):
        # Limit work per tick so verbose commands cannot freeze the window.
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.append(value)
            else:
                self.running = False
                self.run_button.config(state='normal')
                self.choice.config(state='readonly')
                self.open_button.config(state='normal' if any(p.exists() for p in self.outputs) else 'disabled')
                self.status.config(text='Finished — check log' if value == 0 else f'Failed ({value}) — check log')
                self.append('Process finished. Review the log and manifests for skipped/unsupported records.\n' if value == 0 else 'Process failed. Partial output may remain; choose a new output name before retrying.\n')
        self.window.after(100, self.poll)

    def open_output(self):
        for path in self.outputs:
            if path.exists():
                self.open_path(path if path.is_dir() else path.parent)
                return

    def open_path(self, path):
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)])
        except OSError as error:
            messagebox.showerror('Could not open', str(error), parent=self.window)

    def help(self):
        self.open_path(ROOT / ('README.md' if self.tool else 'tools/WORKSHOP_GUI.md'))

    def name_editor(self):
        executable = Path(python_executable())
        if os.name == 'nt' and executable.with_name('pythonw.exe').exists():
            executable = executable.with_name('pythonw.exe')
        try:
            subprocess.Popen([str(executable), str(ROOT / 'formats/cu3/scripts/cu3_name_editor_gui.py')], cwd=ROOT)
        except OSError as error:
            messagebox.showerror('Could not start editor', str(error), parent=self.window)

    def close(self):
        if self.running:
            messagebox.showinfo('Tool is running', 'Let the current operation finish before closing this window.', parent=self.window)
        else:
            self.window.destroy()


def main(tool=None):
    root = tk.Tk()
    Workshop(root, tool=tool)
    root.mainloop()


if __name__ == '__main__':
    main()
