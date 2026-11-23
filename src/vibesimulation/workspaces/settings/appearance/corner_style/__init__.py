"""Setting: corner style."""
from vibesimulation.ui.look.theme import RADII
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Corner style", "Sharp, softly rounded, or pill-shaped buttons.", page.seg("corners", [(r, r) for r in RADII], "Pill", after="look"))
