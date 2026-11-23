"""Setting: digits."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("Multisim", "Significant digits in results", "Precision of voltages, currents and power.", page.combo("digits", 4, (3, 4, 5, 6, 8), sh.apply_settings))
