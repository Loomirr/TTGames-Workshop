"""Smoke test each extracted GUI without relying on the repository checkout."""
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from package_individual_guis import PACKAGES, ROOT, VERSION


def main():
    for name, slug in PACKAGES.items():
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            with ZipFile(ROOT / 'builds/python' / f'{slug}_GUI-{VERSION}.zip') as archive:
                archive.extractall(target)
            script = '''
from pathlib import Path
import runpy, sys, tkinter as tk
sys.path.insert(0, str(Path.cwd()))
original_tk = tk.Tk
def hidden_tk(*args, **kwargs):
    root = original_tk(*args, **kwargs)
    root.withdraw()
    return root
tk.Tk = hidden_tk
tk.Misc.mainloop = lambda self, *a, **k: self.update()
runpy.run_path('Launch.pyw', run_name='__main__')
root = tk._default_root
assert root is not None
def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)
assert not any(w.winfo_class() == 'TCombobox' and w.winfo_manager() and len(w.cget('values')) > 2 for w in children(root))
root.destroy()
for path in Path('formats').rglob('*.py'):
    if path.parent.name == 'scripts':
        sys.path.insert(0, str(path.parent.resolve()))
        runpy.run_path(str(path), run_name='package_smoke')
print('Independent launcher and imports passed')
'''
            result = subprocess.run([sys.executable, '-c', script], cwd=target,
                                    capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(f'{name}: {result.stdout}\n{result.stderr}')
            print(name, 'passed')


if __name__ == '__main__':
    main()
