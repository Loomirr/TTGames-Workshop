"""Decode and select native model draws without requiring Blender.

The CLI audit and Blender assembly deliberately share ownership, validation and
LOD selection. Passing these checks does not establish material/render fidelity.
"""
import hashlib
from pathlib import Path
from .cu3 import FormatError
from .native_mesh import read_mesh
from .native_display import read_display, model_bindings
from .native_materials import read_materials
from .native_layers import selected_layer_metadata
from .skeleton import read_skeleton
from .model_validation import validate_model


def load_model(path, *, skeleton_identity=None):
    path = Path(path)
    def stage(label, reader):
        try:return reader()
        except (FormatError, ValueError) as error:
            raise FormatError(f'{path.name} [{label}]: {error}') from error
    model = stage('mesh decoding', lambda: read_mesh(path))
    model['display'] = stage('display decoding', lambda: read_display(path, len(model['parts'])))
    model['skeleton'] = stage('skeleton decoding', lambda: read_skeleton(
        path, display=model['display'], mesh=model, identity=skeleton_identity)) if path.suffix.lower()=='.ghg' else None
    model['materials'] = stage('material decoding', lambda: read_materials(path)['materials'])
    model['validation'] = stage('decoded model validation', lambda: validate_model(model))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=model['source_sha256']:
        raise FormatError('Native model changed during decoding: '+str(path))
    return model


def selected_draws(model, definition=None, *, layer_mode='authored', highest_detail=True):
    skeleton = model['skeleton']
    if skeleton is None:
        return [(special, binding, None) for special in model['display']['specials']
                for binding in model_bindings(model['display'], special, highest_detail=highest_detail)]
    draws = []
    for metadata in selected_layer_metadata(skeleton, model['display'], definition, layer_mode=layer_mode):
        special = model['display']['specials'][metadata['special']]
        if special['unsupported_commands']:
            raise FormatError('Layer uses unsupported display commands')
        for binding in model_bindings(model['display'], special, highest_detail=highest_detail):
            draws.append((special, binding, metadata))
    return draws
