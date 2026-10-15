"""Check an original HGP through the packaged import operator.

blender -b --factory-startup --python-exit-code 1 --python this.py -- input.hgp new-output
Outputs contain private game data. Choose an ignored folder outside the game.
"""
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import bpy


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    source, output = (Path(value).resolve() for value in args)
    if not source.is_file() or source.suffix.lower() != '.hgp':
        raise ValueError('Supply one original LSW1 PC HGP')
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[4]
    packages = list((root / 'builds/blender').glob('lsw1_hgp_importer-*.zip'))
    if len(packages) != 1:
        raise ValueError('Build exactly one current HGP package first')
    module = output / 'addon' / 'lsw1_hgp_importer'
    with ZipFile(packages[0]) as archive:
        for member in archive.namelist():
            if not (module / member).resolve().is_relative_to(module):
                raise ValueError('Unsafe package member')
        archive.extractall(module)
    sys.path.insert(0, str(module.parent))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import lsw1_hgp_importer as addon
    addon.register()
    try:
        result = bpy.ops.import_scene.lsw1_hgp(filepath=str(source), placement='ORIGIN')
        assert result == {'FINISHED'}, result
        rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.parent]
        assert len(rigs) == 1 and meshes
        assert all(o.data.vertices and o.data.materials and o.data.uv_layers for o in meshes)
        images = [image for image in bpy.data.images if image.type == 'IMAGE' and image.packed_file]
        assert images, 'No packed original textures'
        materials = {m for o in meshes for m in o.data.materials}
        normals = sum(node.type == 'NORMAL_MAP' for m in materials for node in m.node_tree.nodes)
        alpha = sum(link.to_socket.name == 'Alpha' for m in materials for link in m.node_tree.links)
        report = dict(source=str(source), package=packages[0].name, blender=bpy.app.version_string,
                      bones=len(rigs[0].data.bones), meshes=len(meshes), packed_images=len(images),
                      normal_map_nodes=normals, alpha_links=alpha,
                      scope='Packaged operator import and data checks; not an OS drag or in-game check')
        bpy.ops.wm.save_as_mainfile(filepath=str(output / 'Imported.blend'))
        (output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('HGP_OPERATOR_CHECK_PASSED', json.dumps(report))
    finally:
        addon.unregister()


if __name__ == '__main__':
    main()
