"""Setting: side bar position."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Activity bar position", "Show the bar on the left or the right.", page.seg("rail_side", [(x, x) for x in ("Left", "Right")], "Left", after="look"))
