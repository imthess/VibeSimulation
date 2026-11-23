"""Setting: reduce motion."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Reduce motion", "Turn off hover fades and switch animations.", page.switch("reduce_motion", False, "look"))
