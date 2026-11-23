"""Setting: the look of the scanned picture."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Scan look", "Black & white is the cheapest and clearest for line drawings. Grey keeps pencil shading. Colour keeps the original colours.",
             page.seg("scan_look", [("Black & white", "bw"), ("Grey", "gray"), ("Colour", "colour")], "bw", after=lambda: changed(page)))
