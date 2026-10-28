"""Setting file: table bits."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Logisim", "Largest truth table (input bits)", "Bigger circuits show no table (2^bits rows).", page.combo("table_bits", 12, (6, 8, 10, 12, 14, 16), sh.apply_settings))
