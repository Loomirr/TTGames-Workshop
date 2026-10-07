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


def apply_authored_normals(obj, normals):
    """Avoid Blender's legacy normal encoder crash on repeated-index faces.

    Keep the native vertices/triangles intact. The FREE node stores evaluated
    corner normals without constructing the legacy smooth-fan encoding.
    """
    mesh = obj.data
    repeated = any(len(set(face.vertices)) != len(face.vertices) for face in mesh.polygons)
    if not repeated:
        mesh.normals_split_custom_set_from_vertices(normals)
        return
    obj['tt_native_normal_workaround'] = 'Repeated-index faces: evaluated corner normals; native topology preserved'
    if not normal_preservation_status()['supported']:
        obj['tt_native_normal_limitation'] = 'Authored normals on repeated-index faces need the Set Mesh Normal node; using automatic shading'
        return
    automatic = [normal.vector.copy() for normal in mesh.corner_normals]
    attr = mesh.attributes.new(name='TT_NativeNormalPreview',type='FLOAT_VECTOR',domain='CORNER')
    for loop in mesh.loops:
        normal = normals[loop.vertex_index]
        attr.data[loop.index].vector = normal if any(normal) else automatic[loop.index]
    group = bpy.data.node_groups.new('TT native degenerate-face normals','GeometryNodeTree')
    group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes, links = group.nodes, group.links
    source, output = nodes.new('NodeGroupInput'), nodes.new('NodeGroupOutput')
    attribute = nodes.new('GeometryNodeInputNamedAttribute'); attribute.data_type='FLOAT_VECTOR'
    attribute.inputs['Name'].default_value=attr.name
    geometry=restore_normals(nodes,links,source.outputs['Geometry'],attribute.outputs['Attribute'])
    links.new(geometry,output.inputs['Geometry'])
    modifier=obj.modifiers.new('TT native degenerate-face normals','NODES');modifier.node_group=group
