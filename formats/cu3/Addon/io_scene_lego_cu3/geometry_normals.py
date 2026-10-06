"""Keep evaluated corner shading normals through viewing-only geometry changes."""
import bpy


def normal_preservation_status():
    """Expose a fidelity capability separately from successful addon loading."""
    supported = hasattr(bpy.types, 'GeometryNodeSetMeshNormal')
    return dict(supported=supported, required_node='GeometryNodeSetMeshNormal',
                blender_version=list(bpy.app.version),
                limitation=None if supported else
                'This Blender version cannot preserve authored corner normals through facial preview geometry changes.')


def capture_normals(nodes, links, geometry):
    if not normal_preservation_status()['supported']:
        return geometry, None
    capture = nodes.new('GeometryNodeCaptureAttribute'); capture.domain = 'CORNER'
    capture.capture_items.clear(); capture.capture_items.new('VECTOR', 'Native shading normal')
    normal = nodes.new('GeometryNodeInputNormal')
    links.new(geometry, capture.inputs['Geometry'])
    links.new(normal.outputs[0], capture.inputs['Native shading normal'])
    return capture.outputs['Geometry'], capture.outputs['Native shading normal']


def restore_normals(nodes, links, geometry, normal):
    if normal is None:return geometry
    restore = nodes.new('GeometryNodeSetMeshNormal'); restore.mode = 'FREE'; restore.domain = 'CORNER'
    links.new(geometry, restore.inputs['Mesh']); links.new(normal, restore.inputs['Custom Normal'])
    return restore.outputs['Mesh']
