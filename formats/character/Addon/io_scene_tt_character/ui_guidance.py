"""Short, game-specific guidance shared by the sidebar and file picker."""
import textwrap


GAME_GUIDANCE = {
    'LB2': ('PC · NXG', 'Characters and animations; experimental support.'),
    'LB3': ('PC · DX11 models / NXG animations', 'Characters and animations; some parts and materials need work.'),
    'LMSH1': ('PC · NXG', 'Characters and animations; some parts and materials need work.'),
    'HOBBIT': ('PC · NXG', 'Characters and animations; some parts and materials need work.'),
    'AVENGERS': ('PC · DX11', 'Characters and animations; some parts and materials need work.'),
    'LB1': ('PC · Classic', 'Models and rigs only. Costume assembly is incomplete. No animation playback or game export.'),
    'TCS': ('PC · Classic', 'Models and rigs only. Costume assembly is incomplete. No animation playback or game export.'),
    'FORTNITE': ('Static model workflow', 'No animation or game export. A reported import failure is awaiting investigation.'),
}


def note(layout, context, text):
    """Wrap guidance to the sidebar width instead of clipping a long label."""
    region = getattr(context, 'region', None)
    preferences = getattr(context, 'preferences', None)
    system = getattr(preferences, 'system', None)
    scale = max(0.5, getattr(system, 'ui_scale', 1.0))
    width = max(18, int((getattr(region, 'width', 320) / scale - 48) / 7))
    for line in textwrap.wrap(text, width=width):
        layout.label(text=line)


def game_guidance(layout, context, game):
    family, support = GAME_GUIDANCE[game]
    note(layout, context, family)
    note(layout, context, support)
