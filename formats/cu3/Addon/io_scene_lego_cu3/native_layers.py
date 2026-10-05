"""Character-definition selection among alternative HGOL layer specials.

A layer can contain several alternatives (ordinary, robot and skeleton arms,
for example). Character Layer Special selects a named alternative or All;
the observed default is the first special, not every special in the layer.
An unconfigured model inspection retains all specials for inspection.
"""
from .cu3 import FormatError


def selected_layer_metadata(skeleton, display, definition=None, *, layer_mode='authored'):
    if layer_mode not in ('authored', 'default', 'cutscene'):
        raise FormatError('Unknown native layer selection mode')
    selections = {}
    mask = None
    if definition is not None:
        character = definition['character']
        mask = (character.get('Default Layers') if layer_mode == 'default' else character.get('Cutscene Layers')
                if layer_mode == 'cutscene' else character.get('Default Layers') if character.get('Use Default Layers', -1) & 2
                else character.get('Cutscene Layers'))
        for item in definition['objects']:
            if item['class'] != 'Character Layer Special':
                continue
            fields = item['fields']
            # NXG CD v25 calls the same field Layer Id; DX11 calls it Layer.
            index = fields.get('Layer', fields.get('Layer Id'))
            special = fields.get('Layer Special')
            if not isinstance(index, int) or not 0 <= index < 64 or not isinstance(special, str):
                raise FormatError('Invalid character layer-special selection')
            if index in selections and selections[index] != special:
                raise FormatError('Conflicting character layer-special selections')
            selections[index] = special
    result = []
    for index, layer in enumerate(skeleton['layers']):
        if mask is not None and not mask & (1 << index):
            continue
        first = layer['metadata_index']
        last = first + layer['rigids'] + layer['skins']
        if first < 0 or last < first or last > len(skeleton['layer_metadata']):
            raise FormatError('Display layer exceeds native metadata table')
        metadata = skeleton['layer_metadata'][first:last]
        for item in metadata:
            if item['layer'] != index or not 0 <= item['special'] < len(display['specials']):
                raise FormatError('Native layer metadata references an incompatible layer or display instance')
        choice = selections.get(index)
        if definition is None or choice == 'All':
            result.extend(metadata)
        elif choice:
            matching = [m for m in metadata if display['specials'][m['special']]['name'] == choice]
            if len(matching) != 1:
                raise FormatError('Character layer-special name does not identify one native display instance: ' + choice)
            result.extend(matching)
        else:
            result.extend(metadata[:1])
    return result
