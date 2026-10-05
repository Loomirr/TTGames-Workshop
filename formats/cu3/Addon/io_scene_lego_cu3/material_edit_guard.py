"""Detect unsupported material/image edits before copying native sources."""
import hashlib
import json
from .cu3 import FormatError


def scalar(value):
    if isinstance(value,(str,int,float,bool)) or value is None:return value
    try:return list(value)
    except TypeError:return str(value)


def signature(material):
    if material is None:return None
    nodes=[];links=[]
    tree=material.node_tree
    for owner in (material,tree):
        animation=getattr(owner,'animation_data',None)
        if animation and (animation.action or animation.drivers):
            raise FormatError('Animated Blender shader parameters cannot yet be encoded to native material data')
    if tree:
        for node in tree.nodes:
            row=dict(name=node.name,type=node.bl_idname,
                inputs=[scalar(socket.default_value) if hasattr(socket,'default_value') else None for socket in node.inputs],
                outputs=[scalar(socket.default_value) if hasattr(socket,'default_value') else None for socket in node.outputs])
            for field in ('operation','blend_type','uv_map','attribute_name','layer_name','interpolation','projection','projection_blend','extension','space','vector_type'):
                if hasattr(node,field):row[field]=scalar(getattr(node,field))
            image=getattr(node,'image',None)
            if image:
                if image.is_dirty:raise FormatError('Edited Blender image cannot be encoded to its native texture companion: '+image.name)
                row['image']=dict(name=image.name,colorspace=image.colorspace_settings.name,alpha=image.alpha_mode,
                    packed=[hashlib.sha256(packed.packed_file.data).hexdigest() for packed in image.packed_files])
            if getattr(node,'node_tree',None):
                raise FormatError('Custom shader groups are not supported by the native material exporter')
            nodes.append(row)
        links=sorted((link.from_node.name,list(link.from_node.outputs).index(link.from_socket),
                      link.to_node.name,list(link.to_node.inputs).index(link.to_socket)) for link in tree.links)
    fields={name:scalar(getattr(material,name)) for name in ('use_nodes','diffuse_color','surface_render_method') if hasattr(material,name)}
    fields.update(nodes=nodes,links=links)
    return hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bind_materials(obj):
    obj['tt_native_material_baseline']=json.dumps([signature(m) for m in obj.data.materials])


def check_materials(obj):
    # Holdout material replacement is an explicit preview operation. It does
    # not represent a native material edit and is not written to the source.
    if obj.get('tt_colour_write_mask')==0 and obj.get('tt_preview_depth_bias'):
        return
    baseline=obj.get('tt_native_material_baseline')
    if baseline is None:raise FormatError('Reimport with the current addon before exporting native material bindings')
    if [signature(m) for m in obj.data.materials]!=json.loads(baseline):
        raise FormatError('Material edits cannot yet be encoded to native GHG/GSC/TEX data: '+obj.name)
