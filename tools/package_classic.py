"""Include the independently licensed classic inspection backend in addons."""
from pathlib import Path


def add_classic_backend(archive, prefix):
    source=Path(__file__).resolve().parents[1]/'formats/classic-pc'
    for name in ('reader_bounds.py','nu20.py','cu2.py','blender_inspect.py'):
        archive.write(source/'tools'/name,prefix+'/_classic/'+name)
    archive.write(source/'LICENSE',prefix+'/_classic/LICENSE')
    archive.write(source/'README.md',prefix+'/_classic/README.md')
    archive.writestr(prefix+'/_classic/__init__.py','"""Classic PC inspection backend; see LICENSE."""\n')
