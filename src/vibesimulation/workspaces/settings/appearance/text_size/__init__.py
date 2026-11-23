"""Setting: text size."""
from vibesimulation.ui.look.theme import SCALES
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "Text size", "Scales all text in the app  (Ctrl+=  /  Ctrl+-  /  Ctrl+0).", page.seg("text_scale", [(f"{s}%", s) for s in SCALES], 100, int, after="look"))
