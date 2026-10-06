"""Explicit identities for the already enabled PC character profiles.

The selected profile describes the requested asset family, not a detected game
build. Binary readers must still validate their own versions and byte orders.
In particular, LB3 uses NXG animation names with DX11 character models.
"""
from copy import deepcopy
from pathlib import PurePosixPath
from .cu3 import FormatError


CHARACTER_PROFILES = {
    'LMSH1': {'renderer': 'NXG', 'model_suffix': '_NXG', 'animation_suffix': 'NXG',
              'cutscene_version': 18, 'mesh_versions': (169,), 'static_mesh_versions': (161, 169)},
    'LB3': {'renderer': 'DX11', 'model_suffix': '_DX11', 'animation_suffix': 'NXG',
            'cutscene_version': 19, 'mesh_versions': (175,), 'static_mesh_versions': (175,)},
    'HOBBIT': {'renderer': 'NXG', 'model_suffix': '_NXG', 'animation_suffix': 'NXG',
               'cutscene_version': None, 'mesh_versions': (169, 170), 'static_mesh_versions': (169, 170)},
    'AVENGERS': {'renderer': 'DX11', 'model_suffix': '_DX11', 'animation_suffix': 'DX11',
                 'cutscene_version': None, 'mesh_versions': (175,), 'static_mesh_versions': (175,)},
}

# Existing standalone inspection is separate from character-import capability.
# The previous catalog guessed DX11 animation names for LOTR. Its bank/member
# naming needs original evidence; explicit AN4 paths can still be inventoried.
INSPECTION_PROFILES = {
    'TFA': {'renderer':'DX11','model_suffix':'_DX11','animation_suffix':'DX11'},
    'DCSV': {'renderer':'DX11','model_suffix':'_DX11','animation_suffix':'DX11'},
    'LMSH2': {'renderer':'DX11','model_suffix':'_DX11','animation_suffix':'DX11'},
    'LOTR': {'renderer':'NXG','model_suffix':'_NXG','animation_suffix':None},
}


def character_profile(game):
    if game not in CHARACTER_PROFILES:
        raise FormatError('Unsupported character game profile: ' + str(game))
    return deepcopy(CHARACTER_PROFILES[game])


def inspection_profile(game):
    if game in CHARACTER_PROFILES:
        return character_profile(game)
    if game not in INSPECTION_PROFILES:
        raise FormatError('Unsupported reference-inspection game profile: ' + str(game))
    return deepcopy(INSPECTION_PROFILES[game])


def profile_identity(game, *, structure_versions=None, inspection=False):
    profile = inspection_profile(game) if inspection else character_profile(game)
    return {
        'schema': 'tt.profile-identity.v1', 'game': game, 'platform': 'PC',
        'build': None, 'build_status': 'Not established from the supplied source',
        'renderer': profile['renderer'], 'basis': 'Explicitly selected profile; individual layouts remain gated',
        'support_scope':'character_import' if game in CHARACTER_PROFILES else 'reference_inspection_only',
        'model_suffix': profile['model_suffix'], 'animation_suffix': profile['animation_suffix'],
        'structure_versions': dict(structure_versions or {}),
        'structure_byte_orders': {'definition': 'little', 'HGOL': 'big',
                                  'standalone_AN4': 'big', 'embedded_AN4_tree': 'little'},
        'hash_namespaces': {
            'source_sha256': 'Digest of the consumed file bytes; not a native resource identifier',
            'skeleton_binding_sha256': 'Digest of decoded native bind identity; not an AN4 field',
            'archive_path_hash': 'Native archive path identifier; algorithm is archive-layout specific',
            'shader_id': 'Native material/shader identifier; not an archive path hash',
        },
    }


def reference_renderer(reference):
    """Recognize a declared routing suffix only; never infer binary byte order."""
    name = PurePosixPath(str(reference).replace('\\', '/')).name
    stem = PurePosixPath(name).stem if PurePosixPath(name).suffix else name
    for renderer in ('NXG', 'DX11'):
        if stem.casefold().endswith('_' + renderer.casefold()):
            return renderer
    return None


def active_renderer_reference(reference, suffix):
    declared = reference_renderer(reference)
    return declared is None or declared == suffix.lstrip('_').upper()


def require_active_renderer(reference, suffix):
    if not active_renderer_reference(reference, suffix):
        raise FormatError('Resource explicitly selects an inactive renderer: ' + str(reference) +
                          '; active renderer is ' + suffix.lstrip('_'))


def validate_profile_model(game, source, mesh_version):
    profile = character_profile(game)
    require_active_renderer(source, profile['model_suffix'])
    versions = profile['static_mesh_versions'] if PurePosixPath(str(source)).suffix.lower() == '.gsc' else profile['mesh_versions']
    if mesh_version not in versions:
        raise FormatError('Model version does not match the selected game profile: ' + str(mesh_version))
