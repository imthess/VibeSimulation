"""The settings, one file each, in the order they appear on the page."""
from importlib import import_module

ORDER = ['theme',
         'accent_colour',
         'corner_style',
         'glass_look',
         'background',
         'density',
         'text_size',
         'font',
         'side_bar_size',
         'side_bar_position',
         'reduce_motion',
         'high_contrast',
         'status_bar',
         'reset_appearance',
         'auto_open',
         'remember_window',
         'pane_layout',
         'recent_files',
         'table_bits',
         'show_intermediate',
         'play_speed',
         'grid',
         'digits',
         'vibesimulation.workspaces.ai_import.settings.ai_import']      # a name with dots is a full module path (this setting lives with its workspace)


def all_items(page):
    return [import_module(n if n.startswith("vibesimulation.") else f".{n}", __name__).item(page) for n in ORDER]
