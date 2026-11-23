"""Setting: the longest side of the scanned picture."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Scan size (pixels)", "The longest side of the picture that is sent. About 1200 reads well and is cheap; larger helps tiny handwriting. 0 keeps the original size.",
             page.combo("scan_size", 1280, [0, 800, 1000, 1280, 1600, 2000], lambda: changed(page), width=6))
