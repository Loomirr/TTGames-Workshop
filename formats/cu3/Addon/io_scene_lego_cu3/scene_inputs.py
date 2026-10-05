"""Share declared character resource choices between preflight and assembly."""
from .cu3 import FormatError
from .dependencies import ResourceResolver
from .scene_configuration import configuration_report_from_assets, compile_character_replacements


def prepare_resources(cut, assets, profile):
    configuration = configuration_report_from_assets(cut, assets, profile)
    try:
        replacements = compile_character_replacements(configuration)
        configuration['character_resource_map'] = replacements
        configuration['character_resource_map_status'] = 'available'
    except FormatError as error:
        replacements = {}
        configuration['character_resource_map_status'] = 'unresolved'
        configuration['character_resource_map_issue'] = str(error)
    resolver = ResourceResolver(assets, profile, replacements=replacements)
    resolver.validate_cutscene(cut)
    return resolver, configuration
