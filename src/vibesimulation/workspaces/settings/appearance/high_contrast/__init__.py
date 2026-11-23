"""Setting: high contrast."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "High contrast", "Stronger text and border contrast.", page.switch("high_contrast", False, "look"))
