"""Setting: theme."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Theme", "Light, dark, or follow your operating system.", page.seg("mode", (("Light", "light"), ("Dark", "dark"), ("System", "system")), "system", after="look"))
