"""Setting: density."""
from vibesimulation.ui.look.theme import DENSITY
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Density", "How much space there is around controls.", page.seg("density", [(d, d) for d in DENSITY], "Comfortable", after="look"))
