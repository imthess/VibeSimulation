"""Setting: status bar."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Show status bar", "The slim bar at the bottom with shortcut hints.", page.switch("show_status", False))
