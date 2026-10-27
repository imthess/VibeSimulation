"""The settings, one file each, in the order they appear on the page."""
from importlib import import_module

ORDER = ['theme',
         'accent_colour',
         'corner_style',
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
         'ai_import']


def all_items(page):
    return [import_module(f".{n}", __name__).item(page) for n in ORDER]
