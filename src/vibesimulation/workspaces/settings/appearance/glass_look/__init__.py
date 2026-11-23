"""Setting: glass look."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Glass look", "Soft gradient backdrop with frosted, floating panels. Turn it off for flat panels (a little faster on slow computers).", page.switch("glass", True, after="look"))
