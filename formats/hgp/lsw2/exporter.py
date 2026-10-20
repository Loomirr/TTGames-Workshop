"""Write a LEGO Star Wars II model (.hgp) from Blender, to a separate copy based on the original imported file.

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
New bones may be added; existing bone identities and rest transforms are preserved.
"""
import hashlib
import json
import math
import os
import bpy
from mathutils import Vector

from . import hgp
from .exporter_support import pixel_hash
from .importer import to_blender_matrix

TOLERANCE = 1e-6


def to_game_point(v):
    return (v[0], v[2], v[1])


class ExportError(Exception):
    pass


def collect(arm):
    """Mesh objects that become parts: every mesh parented to the armature (imported or new)."""
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == arm]
    return sorted(objs, key=lambda o: (o.get('lsw2_part', 1 << 30), o.name))


def part_place(obj, bone_index):
    """(layer, slot, bone) of an object: a mesh parented to a bone is a rigid part on that bone; any
    other is skinned. The layer is the object's `lsw2_layer`, else that of its layer collection."""
    layer = obj.get('lsw2_layer')
    if layer is None:
        for col in obj.users_collection:
            if 'lsw2_layer' in col:
                layer = col['lsw2_layer']
                break
    if layer is None:
        raise ExportError(f'{obj.name}: put it in one of the model\'s layer collections '
                          f'(or give it an lsw2_layer property)')
    if obj.parent_type == 'BONE' and obj.parent_bone:
        if obj.parent_bone not in bone_index:
            raise ExportError(f'{obj.name}: parented to unknown bone {obj.parent_bone}')
        return int(layer), 'rigid', bone_index[obj.parent_bone]
    slot = str(obj.get('lsw2_slot', 'skinned'))
    if slot == 'rigid':                     # a rigid part that lost its bone parent
        raise ExportError(f'{obj.name}: a rigid part must stay parented to a bone')
    return int(layer), slot, None


def mesh_in_part_space(obj, arm, model, worlds, rigid_bone=None):
    """Vertex positions in the space the file stores them in (model space, or the bone's for rigid)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    # rest-pose geometry without the armature deformation
    mods = [m for m in obj.modifiers if m.type == 'ARMATURE' and m.show_viewport]
    for m in mods:
        m.show_viewport = False
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
    values = [(k, k.value, k.mute) for k in keys]
    for k in keys:
        k.value = 0.0
    pinned = obj.show_only_shape_key
    obj.show_only_shape_key = False
    try:
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mesh = mesh.copy()
        eval_obj.to_mesh_clear()
    finally:
        for m in mods:
            m.show_viewport = True
        for k, value, mute in values:
            k.value, k.mute = value, mute
        obj.show_only_shape_key = pinned
    if rigid_bone is not None:
        target = arm.matrix_world @ worlds[rigid_bone]
    else:
        target = arm.matrix_world
    delta = target.inverted() @ obj.matrix_world
    identity = all(abs(delta[r][c] - (1.0 if r == c else 0.0)) < 1e-6 for r in range(4) for c in range(4))
    if not identity:
        mesh.transform(delta)
    return mesh, identity


def delta_linear(obj, arm, worlds, rigid_bone):
    target = arm.matrix_world @ worlds[rigid_bone] if rigid_bone is not None else arm.matrix_world
    return (target.inverted() @ obj.matrix_world).to_3x3()


def gather_shapes(obj, mesh, linear, vertex_of):
    """Facial shapes from shape keys: [(id, offsets per file vertex or None)], or None if there are none.

    Keys named `morph <n>` go back to slot n with the id recorded at import (a missing key leaves
    its slot empty); any other key is added as a new shape after them."""
    keys = obj.data.shape_keys
    if keys and len(keys.key_blocks) > 1 and any(
            m.show_viewport and m.type != 'ARMATURE' for m in obj.modifiers):
        raise ExportError(f'{obj.name}: apply non-armature modifiers consistently to Basis and every shape key before export')
    ids = list(obj.get('lsw2_morph_ids', []))
    if not keys or len(keys.key_blocks) < 2:
        # no keys: no shapes, unless the part came with slots (some originals hold only empty ones)
        return [(i, None) for i in ids] or None
    if len(mesh.vertices) != len(obj.data.vertices):
        raise ExportError(f'{obj.name}: its modifiers change the vertex count, so its shape keys cannot be '
                          f'matched to the exported vertices (apply the modifiers first)')
    ref = keys.reference_key
    basis = [v.co.copy() for v in ref.data]
    slots = {k: None for k in range(len(ids))}
    extra = []
    for kb in keys.key_blocks:
        if kb == ref:
            continue
        deltas = [linear @ (kb.data[vi].co - basis[vi]) for vi in vertex_of]
        deltas = [(d.x, d.z, d.y) for d in deltas]
        name = kb.name
        if name.startswith('morph ') and name[6:].isdigit() and int(name[6:]) in slots:
            slots[int(name[6:])] = deltas
        else:
            extra.append(deltas)
    shapes = [(ids[k], slots[k]) for k in range(len(ids))]
    next_id = max(ids, default=-1) + 1
    for d in extra:
        shapes.append((next_id, d))
        next_id += 1
    return shapes


def gather_part(obj, arm, model, worlds, bone_index, rigid_bone=None):
    """Vertices, triangles and weights of one object, in the file's terms."""
    mesh, _ = mesh_in_part_space(obj, arm, model, worlds, rigid_bone)
    try:
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active
        normals = [Vector(n.vector) for n in mesh.corner_normals]
        if (any(not math.isfinite(x) for v in mesh.vertices for x in v.co)
                or any(not math.isfinite(x) for n in normals for x in n)
                or (uv_layer and any(not math.isfinite(x) for v in uv_layer.data for x in v.uv))
                or any(not math.isfinite(g.weight) for v in mesh.vertices for g in v.groups)):
            raise ExportError(f'{obj.name}: geometry contains non-finite positions, normals, UVs or weights')
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
                # Native vertices carry one normal. Split hard edges as well as UV seams.
                key = (vi, round(uv[0], 6), round(uv[1], 6))
                candidates = key_to_index.setdefault(key, [])
                idx = next((i for i, n in candidates
                            if max(abs(a-b) for a, b in zip(n, normals[li])) <= 1e-4), None)
                if idx is not None:
                    normal_sum[idx] += normals[li]
                else:
                    idx = len(positions)
                    candidates.append((idx, Vector(normals[li])))
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
        shapes = gather_shapes(obj, mesh, delta_linear(obj, arm, worlds, rigid_bone), [keys_vi[i] for i in order])
        return pick(positions), pick(out_normals), pick(uvs), pick(colours), pick(weights), triangles, shapes
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


def same_shapes(a, b):
    a, b = a or [], b or []
    if len(a) != len(b):
        return False
    for (ia, da), (ib, db) in zip(a, b):
        if ia != ib or (da is None) != (db is None):
            return False
        if da is not None and (len(da) != len(db) or
                any(len(u) != len(v) or any(not math.isfinite(x) or not math.isfinite(y)
                    or abs(x - y) > 1e-5 for x, y in zip(u, v)) for u, v in zip(da, db))):
            return False
    return True


def matches_original(orig, positions, normals, uvs, weights, triangles, shapes=None, colours=None):
    if any(not math.isfinite(x) for rows in (positions, normals, uvs) for row in rows for x in row) or \
            any(not math.isfinite(w) for slots in weights for _, w in slots):
        raise ExportError('Geometry contains non-finite positions, normals, UVs or weights')
    if len(orig.positions) != len(positions):
        return False
    if colours is None or list(orig.colours) != list(colours):
        return False
    if len(normals) != len(orig.normals) or len(uvs) != len(orig.uvs):
        return False
    for old, new in zip(orig.normals, normals):
        length = math.sqrt(sum(x*x for x in old))
        expected = tuple(x / length for x in old) if length > 1e-12 else old
        # Blender's encoded custom normals introduce roughly 5e-5 round-trip error.
        if len(new) != 3 or any(not math.isfinite(b) or abs(a-b) > 1e-4
                                for a, b in zip(expected, new)):
            return False
    if not same_shapes(orig.shapes, shapes):
        return False
    if any(abs(a - b) > TOLERANCE for p, q in zip(orig.positions, positions) for a, b in zip(p, q)):
        return False
    if any(abs(a - b) > 1e-5 for p, q in zip(orig.uvs, uvs) for a, b in zip(p, q)):
        return False
    norm = lambda ts: sorted(t[t.index(min(t)):] + t[:t.index(min(t))] for t in map(tuple, ts))
    if norm(orig.triangles()) != norm(triangles):
        return False
    if orig.kind == hgp.SKINNED:
        if len(orig.weights) != len(weights):
            return False
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


def split_by_bones(positions, normals, uvs, colours, weights, triangles, shapes=None):
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
                        shapes=None if shapes is None else
                        [(sid, None if d is None else [d[v] for v in order]) for sid, d in shapes],
                        triangles=[tuple(remap[v] for v in t) for t in g['tris']]))
    return out


def linear_to_srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def read_material(mat):
    """(colour as stored, alpha, image or None) from a material: the importer's node setup or a plain
    Principled BSDF whose Base Color is a value, an image, or a Mix of a colour and an image."""
    colour, alpha, image = (1.0, 1.0, 1.0), 1.0, None
    tree = mat.node_tree if mat.use_nodes else None
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if tree else None
    if bsdf is None:
        c = mat.diffuse_color
        return tuple(linear_to_srgb(x) for x in c[:3]), c[3], None
    alpha_in = bsdf.inputs['Alpha']
    alpha = alpha_in.default_value
    if alpha_in.is_linked and alpha_in.links[0].from_node.type == 'MATH':
        alpha = alpha_in.links[0].from_node.inputs[1].default_value      # texture alpha x opacity
    base = bsdf.inputs['Base Color']
    if not base.is_linked:
        return tuple(linear_to_srgb(x) for x in base.default_value[:3]), alpha, None
    src = base.links[0].from_node
    if src.type == 'TEX_IMAGE':
        return colour, alpha, src.image
    if src.type == 'MIX':
        a = src.inputs['A']
        colour = tuple(linear_to_srgb(x) for x in a.default_value[:3])
        b = src.inputs['B']
        if b.is_linked and b.links[0].from_node.type == 'TEX_IMAGE':
            image = b.links[0].from_node.image
    return colour, alpha, image


def image_rgba(img):
    """uint8 RGBA, top row first, at the power-of-two size the file will hold (resampled bilinearly
    from the image's own pixels; a copy of an unsaved image would lose its edits)."""
    import numpy as np
    from . import dxt
    sw, sh = img.size
    w, h = dxt.power_of_two_size(sw, sh)
    px = np.empty(sw * sh * img.channels, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(sh, sw, img.channels)
    if img.channels < 4:
        px = np.concatenate([px[..., :3] if img.channels >= 3 else np.repeat(px[..., :1], 3, 2),
                             np.ones((sh, sw, 1), np.float32)], 2)
    if (w, h) != (sw, sh):
        ys = np.clip((np.arange(h) + 0.5) * sh / h - 0.5, 0, sh - 1)
        xs = np.clip((np.arange(w) + 0.5) * sw / w - 0.5, 0, sw - 1)
        y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
        y1, x1 = np.minimum(y0 + 1, sh - 1), np.minimum(x0 + 1, sw - 1)
        fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
        top = px[y0][:, x0] * (1 - fx) + px[y0][:, x1] * fx
        bottom = px[y1][:, x0] * (1 - fx) + px[y1][:, x1] * fx
        px = top * (1 - fy) + bottom * fy
    rgba = np.clip(np.rint(px * 255), 0, 255).astype(np.uint8)[::-1]
    return np.ascontiguousarray(rgba)


def encode_texture(img):
    from . import dxt
    rgba = image_rgba(img)
    h, w = rgba.shape[:2]
    return dict(width=w, height=h, levels=1, format=dxt.FORMAT_DXT5,
                dds=dxt.dds_file(w, h, dxt.encode_dxt5(rgba)))


def game_world(bone):
    """A Blender bone's rest matrix as a game row-major world matrix."""
    from .importer import SWAP
    m = SWAP @ bone.matrix_local @ SWAP
    return [m[c][r] for r in range(4) for c in range(4)]


def export_hgp(context, filepath, arm, source=None, report=print):
    # the file holds the rest pose: an animated or posed armature must not move the parts
    position = arm.data.pose_position
    arm.data.pose_position = 'REST'
    context.view_layer.update()
    try:
        return _export(context, filepath, arm, source, report)
    finally:
        arm.data.pose_position = position
        context.view_layer.update()


def _export(context, filepath, arm, source, report):
    source = source or arm.get('lsw2_source')
    if not source:
        raise ExportError('No original .hgp: import the model with this add-on, or choose the original file')
    if os.path.normcase(os.path.realpath(filepath)) == os.path.normcase(os.path.realpath(source)) or (
            os.path.exists(filepath) and os.path.samefile(filepath, source)):
        raise ExportError('Export to a separate file; the imported source must remain unchanged')
    with open(source, 'rb') as f:
        source_data = f.read()
    if arm.get('lsw2_source_sha256') != hashlib.sha256(source_data).hexdigest():
        raise ExportError('Original source identity does not match this import. Reimport the original HGP first')
    model = hgp.Model(source_data)
    notes = []

    # bones: the originals by their stored number, then any new ones (parents first)
    bone_index = {}
    for b in arm.data.bones:
        if 'lsw2_bone' in b:
            bone_index[b.name] = int(b['lsw2_bone'])
    if sorted(bone_index.values()) != list(range(len(model.bones))):
        raise ExportError('The armature does not hold every original bone (bones can be added, not removed)')
    try:
        snapshot = json.loads(arm['lsw2_imported_rig'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ExportError('Missing imported rig identity; reimport the original HGP first') from exc
    if len(snapshot) != len(model.bones):
        raise ExportError('Imported rig identity does not match the original skeleton')
    for b in arm.data.bones:
        if b.name not in bone_index:
            continue
        old = snapshot[bone_index[b.name]]
        matrix = [x for row in b.matrix_local for x in row]
        if (b.name != old['name'] or (b.parent.name if b.parent else None) != old['parent']
                or len(old['matrix']) != 16 or any(not math.isfinite(x) or abs(x-y) > 1e-5
                     for x, y in zip(matrix, old['matrix']))):
            raise ExportError(f'{b.name}: editing an original bone name, parent or rest transform is not supported')
    bones = list(model.bones)
    new_bones = [b for b in arm.data.bones if 'lsw2_bone' not in b]
    depth = lambda b: 0 if b.parent is None else 1 + depth(b.parent)
    for b in sorted(new_bones, key=depth):
        world = game_world(b)
        parent = bone_index[b.parent.name] if b.parent else -1
        if parent >= 0:
            parent_world = hgp._bone_world(bones, parent) if parent >= len(model.bones) else bones[parent]['world']
            local = hgp._mul(world, hgp._inverse(parent_world))
        else:
            local = world
        try:
            name = b.name.encode('ascii', 'strict').decode('ascii')
        except UnicodeError as exc:
            raise ExportError(f'{b.name}: new bone names must be ASCII; rename it explicitly') from exc
        if not name or '\x00' in name or name in {bone['name'] for bone in bones}:
            raise ExportError(f'{b.name}: new bone name is empty, invalid or duplicates a native name')
        bone_index[b.name] = len(bones)
        bones.append(dict(name=name, parent=parent, local=local))
    if new_bones:
        notes.append(f'{len(new_bones)} new bone(s) added after the original {len(model.bones)}')
    worlds = [to_blender_matrix(b['world']) for b in model.bones] + \
             [to_blender_matrix(hgp._bone_world(bones, i)) for i in range(len(model.bones), len(bones))]

    # textures and materials
    textures = list(model.textures)
    image_texture = {}
    # Copies made in Blender inherit custom properties. Multiple datablocks may
    # therefore claim the same native slot even within one source. Allocate all
    # such claimants separately so their order cannot overwrite another part.
    material_claims, texture_claims = {}, {}
    for obj in collect(arm):
        for mat in obj.data.materials:
            if mat is None:
                continue
            if mat.get('lsw2_source_sha256') == arm['lsw2_source_sha256']:
                material_claims.setdefault(mat.get('lsw2_material'), set()).add(mat.name)
            image = read_material(mat)[2]
            if image is not None and image.get('lsw2_source_sha256') == arm['lsw2_source_sha256']:
                texture_claims.setdefault(image.get('lsw2_texture'), set()).add(image.name)

    def texture_of(img):
        if img is None:
            return None
        if img.name in image_texture:
            return image_texture[img.name]
        idx = img.get('lsw2_texture') if img.get('lsw2_source_sha256') == arm['lsw2_source_sha256'] else None
        if len(texture_claims.get(idx, ())) > 1:
            idx = None
        if idx is not None and img.get('lsw2_pixels') == pixel_hash(img) and 0 <= idx < len(model.textures):
            result = int(idx)
        elif idx is not None and 0 <= idx < len(model.textures):
            textures[int(idx)] = encode_texture(img)          # an original image that was painted
            result = int(idx)
            notes.append(f'texture {idx} ({img.name}) re-encoded as DXT5')
        else:
            textures.append(encode_texture(img))
            result = len(textures) - 1
            notes.append(f'new texture {result} from {img.name}')
        image_texture[img.name] = result
        return result

    materials = [dict(m) for m in model.materials]
    material_of = {}

    def material_index(mat):
        if mat.name in material_of:
            return material_of[mat.name]
        colour, alpha, image = read_material(mat)
        tex = texture_of(image)
        idx = mat.get('lsw2_material') if mat.get('lsw2_source_sha256') == arm['lsw2_source_sha256'] else None
        if len(material_claims.get(idx, ())) > 1:
            idx = None
        if idx is not None and 0 <= idx < len(model.materials):
            m = materials[int(idx)]
            if max(abs(a - b) for a, b in zip(colour, m['colour'])) > 2e-3:
                m['colour'] = tuple(colour)
            if abs(alpha - m['alpha']) > 1e-4:
                m['alpha'] = alpha
            m['texture'] = tex
            result = int(idx)
        else:
            plain = [i for i, m in enumerate(model.materials) if m['linked'] is None
                     and (m['texture'] is None) == (tex is None)] or list(range(len(model.materials)))
            materials.append(dict(template=plain[0], colour=tuple(colour), alpha=alpha, texture=tex, linked=None))
            result = len(materials) - 1
            notes.append(f'new material {result} from {mat.name}')
        material_of[mat.name] = result
        return result

    used_originals = set()
    parts = []
    for obj in collect(arm):
        layer, slot, rigid_bone = part_place(obj, bone_index)
        if not 0 <= layer < len(model.layers):
            raise ExportError(f'{obj.name}: layer {layer} does not exist in the original')
        if not obj.data.materials or obj.data.materials[0] is None:
            raise ExportError(f'{obj.name}: no material')
        mat = obj.data.materials[0]
        if any(poly.material_index != 0 for poly in obj.data.polygons):
            raise ExportError(f'{obj.name}: separate faces using different materials into different mesh objects')
        mat_idx = material_index(mat)
        kind = hgp.RIGID if slot == 'rigid' else hgp.SKINNED
        positions, normals, uvs, colours, weights, triangles, shapes = gather_part(
            obj, arm, model, worlds, bone_index, rigid_bone)
        if not triangles:
            notes.append(f'{obj.name}: no faces, left out')
            continue
        index = obj.get('lsw2_part') if obj.get('lsw2_source_sha256') == arm['lsw2_source_sha256'] else None
        orig = model.parts[index] if index is not None and 0 <= index < len(model.parts) else None
        if orig is not None and (orig.layer != layer or orig.slot != slot or orig.bone != rigid_bone
                                 or index in used_originals):
            orig = None
        if kind == hgp.SKINNED:
            weights = [tidy_weights(w, i, obj.name) for i, w in enumerate(weights)]
        if orig is not None and orig.material == mat_idx and \
                matches_original(orig, positions, normals, uvs, weights, triangles, shapes, colours):
            used_originals.add(index)
            parts.append(orig)
            continue
        template = orig.template if orig is not None else model.template_for(kind)
        buffer = orig.buffer if orig is not None else model.buffer_for(kind)
        pieces = split_by_bones(positions, normals, uvs, colours, weights, triangles, shapes) \
            if kind == hgp.SKINNED else [dict(palette=[], positions=positions, normals=normals, uvs=uvs,
                                              colours=colours, weights=[], triangles=triangles, shapes=shapes)]
        if len(pieces) > 1:
            notes.append(f'{obj.name}: split into {len(pieces)} parts (at most {hgp.MAX_BONES_PER_PART} bones each)')
        for k, piece in enumerate(pieces):
            p = hgp.Part()
            p.layer, p.slot, p.kind, p.bone = layer, slot, kind, rigid_bone
            p.material = mat_idx
            p.buffer = buffer
            p.template = template
            p.palette = piece['palette']
            p.positions, p.normals, p.uvs = piece['positions'], piece['normals'], piece['uvs']
            p.colours, p.weights = piece['colours'], piece['weights']
            p.set_triangles(piece['triangles'])
            p.shapes = piece['shapes']
            if orig is not None and k == 0:
                used_originals.add(index)
                p.offset, p.original = orig.offset, orig.original
                p.morph, p.morph_vertices = orig.morph, orig.morph_vertices
            parts.append(p)
    dropped = len(model.parts) - len(used_originals)
    if dropped:
        notes.append(f'{dropped} original part(s) not in the scene were left out')
    data = model.write(parts, textures=textures, bones=bones, materials=materials)
    hgp.Model(data)        # the written file must read back
    with open(filepath, 'wb') as f:
        f.write(data)
    for n in notes:
        report(n)
    return data, notes
