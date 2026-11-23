"""The settings in the order they appear on the page. Each one is a folder ``<category>/<setting>/`` whose ``__init__.py`` has ``item(page)``."""
from importlib import import_module

ORDER = ['appearance.theme',
         'appearance.accent_colour',
         'appearance.corner_style',
         'appearance.glass_look',
         'appearance.background',
         'appearance.density',
         'appearance.text_size',
         'appearance.font',
         'appearance.side_bar_size',
         'appearance.side_bar_position',
         'appearance.reduce_motion',
         'appearance.high_contrast',
         'appearance.status_bar',
         'appearance.ai_button',
         'appearance.reset_appearance',
         'general.auto_open',
         'general.remember_window',
         'general.pane_layout',
         'general.recent_files',
         'logisim.table_bits',
         'logisim.show_intermediate',
         'logisim.play_speed',
         'logisim.grid',
         'multisim.digits',
         'ai_import.models',
         'ai_import.default_convert_to',
         'ai_import.separate_ai',
         'ai_import.limit_reasoning',
         'ai_import.compact_answer',
         'ai_import.openrouter_pick',
         'ai_import.scan_on_import',
         'ai_import.scan_crop',
         'ai_import.scan_flatten',
         'ai_import.scan_look',
         'ai_import.scan_contrast',
         'ai_import.scan_ink',
         'ai_import.scan_size']


def all_items(page):
    return [import_module(f"{__package__}.{n}").item(page) for n in ORDER]
