"""Write a LEGO Star Wars II model (.hgp) from Blender, on top of the original file it was imported from.

The original (the armature's `lsw2_source`, or a file chosen in the export dialog) supplies everything
this add-on does not edit: skeleton, materials, textures, attachment points, morph data and the
structures not yet understood. From Blender come the parts: every mesh object under the armature
that carries `lsw2_layer` and `lsw2_slot`.

- A part that still matches its original (same vertices, triangles, UVs, weights) is written as the
  original, so an unchanged import writes back an identical file.
- An edited part is rebuilt from the mesh: triangulated, split into vertices per distinct UV and
  normal, weights limited to the three strongest bones (normalised), and split into several parts
  when it uses more than eight bones (the most any original part uses).
- A new or duplicated object becomes a new part in its layer and slot, modelled on an existing part.
Bones cannot be added: weights must name bones of the original skeleton.
"""
import bpy
from mathutils import Vector

from . import hgp
from .importer import to_blender_matrix

TOLERANCE = 1e-6


def to_game_point(v):
    return (v[0], v[2], v[1])


class ExportError(Exception):
    pass


def collect(arm):
    objs = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.parent == arm and 'lsw2_slot' in obj and 'lsw2_layer' in obj:
            objs.append(obj)
    return sorted(objs, key=lambda o: (o.get('lsw2_part', 1 << 30), o.name))


def mesh_in_part_space(obj, arm, model, worlds):
    """Vertex positions in the space the file stores them in (model space, or the bone's for rigid)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    # rest-pose geometry without the armature deformation
    mods = [m for m in obj.modifiers if m.type == 'ARMATURE' and m.show_viewport]
    for m in mods:
        m.show_viewport = False
    try:
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mesh = mesh.copy()
        eval_obj.to_mesh_clear()
    finally:
        for m in mods:
            m.show_viewport = True
    if obj['lsw2_slot'] == 'rigid':
        bone = int(obj['lsw2_bone'])
        target = arm.matrix_world @ worlds[bone]
    else:
        target = arm.matrix_world
    delta = target.inverted() @ obj.matrix_world
    identity = all(abs(delta[r][c] - (1.0 if r == c else 0.0)) < 1e-6 for r in range(4) for c in range(4))
    if not identity:
        mesh.transform(delta)
    return mesh, identity


def gather_part(obj, arm, model, worlds, bone_index):
    """Vertices, triangles and weights of one object, in the file's terms."""
    mesh, _ = mesh_in_part_space(obj, arm, model, worlds)
    try:
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active
        normals = [Vector(n.vector) for n in mesh.corner_normals]
        colour_attr = mesh.attributes.get('lsw2_colour')
        group_bone = {}
        for g in obj.vertex_groups:
            if g.name in bone_index:
                group_bone[g.index] = bone_index[g.name]
        key_to_index, positions, out_normals, uvs, colours, weights = {}, [], [], [], [], []
        triangles, keys_vi, normal_sum = [], [], []
        for tri in mesh.loop_triangles:
            corner = []
            for li in tri.loops:
                vi = mesh.loops[li].vertex_index
                uv = tuple(uv_layer.data[li].uv) if uv_layer else (0.0, 0.0)
                # the file keeps one normal per vertex: one file vertex per Blender vertex and UV, with
                # the mean of its corners' normals (split an edge in Blender to make it hard)
                key = (vi, round(uv[0], 6), round(uv[1], 6))
                idx = key_to_index.get(key)
                if idx is not None:
                    normal_sum[idx] += normals[li]
                else:
                    idx = key_to_index[key] = len(positions)
                    keys_vi.append(vi)
                    normal_sum.append(Vector(normals[li]))
                    positions.append(to_game_point(mesh.vertices[vi].co))
                    out_normals.append(None)
                    uvs.append((uv[0], 1.0 - uv[1]))
                    c = colour_attr.data[vi].value if colour_attr else -16777216
                    colours.append(c & 0xFFFFFFFF)
                    slots = []
                    for ge in mesh.vertices[vi].groups:
                        if ge.group in group_bone and ge.weight > 0:
                            slots.append((group_bone[ge.group], ge.weight))
                    weights.append(slots)
                corner.append(idx)
            a, c, b = corner              # Blender winding back to the file's
            triangles.append((a, b, c))
        for i, n in enumerate(normal_sum):
            out_normals[i] = to_game_point(n.normalized() if n.length > 1e-12 else Vector((0, 0, 1)))
        # number the file's vertices in Blender vertex order, so an unchanged mesh keeps the original order
        order = sorted(range(len(positions)), key=lambda i: (keys_vi[i], i))
        new = {old: k for k, old in enumerate(order)}
        pick = lambda seq: [seq[i] for i in order]
        triangles = [tuple(new[v] for v in t) for t in triangles]
        return pick(positions), pick(out_normals), pick(uvs), pick(colours), pick(weights), triangles
    finally:
        bpy.data.meshes.remove(mesh)


def tidy_weights(slots, vertex, obj_name):
    merged = {}
    for b, w in slots:
        merged[b] = merged.get(b, 0.0) + w
    best = sorted(merged.items(), key=lambda bw: -bw[1])[:3]
    total = sum(w for _, w in best)
    if total <= 0:
        raise ExportError(f'{obj_name}: vertex {vertex} has no weight on any bone of the skeleton')
    return [(b, w / total) for b, w in best]


def matches_original(orig, positions, normals, uvs, weights, triangles):
    if len(orig.positions) != len(positions):
        return False
    if any(abs(a - b) > TOLERANCE for p, q in zip(orig.positions, positions) for a, b in zip(p, q)):
        return False
    if any(abs(a - b) > 1e-5 for p, q in zip(orig.uvs, uvs) for a, b in zip(p, q)):
        return False
    norm = lambda ts: sorted(t[t.index(min(t)):] + t[:t.index(min(t))] for t in map(tuple, ts))
    if norm(orig.triangles()) != norm(triangles):
        return False
    if orig.kind == hgp.SKINNED:
        for w0, w1 in zip(orig.weights, weights):
            a = {}
            for b, w in w0:
                a[b] = a.get(b, 0) + w
            b_ = {}
            for b, w in w1:
                b_[b] = b_.get(b, 0) + w
            if a.keys() != b_.keys() or any(abs(a[k] - b_[k]) > 1e-4 for k in a):
                return False
    return True


def split_by_bones(positions, normals, uvs, colours, weights, triangles):
    """Groups of triangles that each use at most MAX_BONES_PER_PART bones."""
    groups = []
    for t in triangles:
        bones = {b for v in t for b, _ in weights[v]}
        for g in groups:
            if len(g['bones'] | bones) <= hgp.MAX_BONES_PER_PART:
                g['bones'] |= bones
                g['tris'].append(t)
                break
        else:
            if len(bones) > hgp.MAX_BONES_PER_PART:
                raise ExportError(f'A triangle uses {len(bones)} bones')
            groups.append(dict(bones=set(bones), tris=[t]))
    out = []
    for g in groups:
        order = sorted({v for t in g['tris'] for v in t})      # keep the vertices' order
        remap = {v: k for k, v in enumerate(order)}
        out.append(dict(palette=sorted(g['bones']),
                        positions=[positions[v] for v in order], normals=[normals[v] for v in order],
                        uvs=[uvs[v] for v in order], colours=[colours[v] for v in order],
                        weights=[weights[v] for v in order],
                        triangles=[tuple(remap[v] for v in t) for t in g['tris']]))
    return out


def template_for(model, layer, slot, kind):
    same = [p for p in model.parts if p.layer == layer and p.slot == slot] or \
           [p for p in model.parts if p.kind == kind]
    if not same:
        raise ExportError(f'The original has no {slot} part to model a new one on')
    return same[0]


def export_hgp(context, filepath, arm, source=None, report=print):
    source = source or arm.get('lsw2_source')
    if not source:
        raise ExportError('No original .hgp: import the model with this add-on, or choose the original file')
    with open(source, 'rb') as f:
        model = hgp.Model(f.read())
    worlds = [to_blender_matrix(b['world']) for b in model.bones]
    bone_index = {}
    for b in arm.data.bones:
        if 'lsw2_bone' in b:
            bone_index[b.name] = int(b['lsw2_bone'])
    if len(bone_index) != len(model.bones):
        raise ExportError('The armature does not match the original skeleton')
    material_index = {}
    for i, m in enumerate(bpy.data.materials):
        if 'lsw2_material' in m:
            material_index[m.name] = int(m['lsw2_material'])

    parts, notes = [], []
    used_originals = set()
    for obj in collect(arm):
        layer, slot = int(obj['lsw2_layer']), str(obj['lsw2_slot'])
        if not 0 <= layer < len(model.layers):
            raise ExportError(f'{obj.name}: layer {layer} does not exist in the original')
        if not obj.data.materials or obj.data.materials[0] is None:
            raise ExportError(f'{obj.name}: no material')
        mat = obj.data.materials[0]
        if mat.name not in material_index:
            raise ExportError(f'{obj.name}: material {mat.name} is not one of the original model\'s')
        if len(obj.data.materials) > 1:
            notes.append(f'{obj.name}: only its first material is exported')
        kind = hgp.RIGID if slot == 'rigid' else hgp.SKINNED
        positions, normals, uvs, colours, weights, triangles = gather_part(obj, arm, model, worlds, bone_index)
        if not triangles:
            notes.append(f'{obj.name}: no faces, left out')
            continue
        index = obj.get('lsw2_part')
        orig = model.parts[index] if index is not None and 0 <= index < len(model.parts) else None
        if orig is not None and (orig.layer != layer or orig.slot != slot or index in used_originals):
            orig = None
        if kind == hgp.SKINNED:
            weights = [tidy_weights(w, i, obj.name) for i, w in enumerate(weights)]
        if orig is not None and orig.material == material_index[mat.name] and \
                matches_original(orig, positions, normals, uvs, weights, triangles):
            used_originals.add(index)
            parts.append(orig)
            continue
        template = orig or template_for(model, layer, slot, kind)
        pieces = split_by_bones(positions, normals, uvs, colours, weights, triangles) if kind == hgp.SKINNED \
            else [dict(palette=[], positions=positions, normals=normals, uvs=uvs, colours=colours,
                       weights=[], triangles=triangles)]
        if len(pieces) > 1:
            notes.append(f'{obj.name}: split into {len(pieces)} parts (at most {hgp.MAX_BONES_PER_PART} bones each)')
        for k, piece in enumerate(pieces):
            p = hgp.Part()
            p.layer, p.slot, p.kind = layer, slot, kind
            p.bone = int(obj['lsw2_bone']) if slot == 'rigid' else None
            p.material = material_index[mat.name]
            p.buffer = template.buffer
            p.template = template.template
            p.palette = piece['palette']
            p.positions, p.normals, p.uvs = piece['positions'], piece['normals'], piece['uvs']
            p.colours, p.weights = piece['colours'], piece['weights']
            p.set_triangles(piece['triangles'])
            if orig is not None and k == 0:
                used_originals.add(index)
                p.offset, p.original = orig.offset, orig.original
                if orig.morph is not None:
                    if len(p.positions) == orig.morph_vertices:
                        p.morph, p.morph_vertices = orig.morph, orig.morph_vertices
                    else:
                        notes.append(f'{obj.name}: its vertices changed, so its facial shapes were dropped')
            parts.append(p)
    # a rigid part must go to a bone whose object exists in the original
    have = {(o['layer'], o['slot'], o['bone']) for o in model.objects}
    for p in parts:
        if (p.layer, p.slot, p.bone) not in have:
            raise ExportError(f'Layer {p.layer} has no {p.slot} list for bone {p.bone} in the original; '
                              f'parent the part to a bone that already carries a rigid part in that layer')
    dropped = len(model.parts) - len(used_originals)
    if dropped:
        notes.append(f'{dropped} original part(s) not in the scene were left out')
    data = model.write(parts)
    hgp.Model(data)        # the written file must read back
    with open(filepath, 'wb') as f:
        f.write(data)
    for n in notes:
        report(n)
    return data, notes
