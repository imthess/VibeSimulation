"""Setting file: digits."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Multisim", "Significant digits in results", "Precision of voltages, currents and power.", page.combo("digits", 4, (3, 4, 5, 6, 8), sh.apply_settings))
