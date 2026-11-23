"""Setting: scan contrast."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.ai_import.controls import slider
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Scan contrast", "Higher = harder, blacker lines and a whiter page. Lower = softer.", slider(page, "scan_contrast", 50, "Contrast", lambda: changed(page)))
