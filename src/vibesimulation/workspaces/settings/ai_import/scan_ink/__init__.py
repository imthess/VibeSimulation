"""Setting: how faint a stroke may be and still be kept."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.ai_import.controls import slider
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Scan line strength", "Higher keeps fainter pencil lines (and more dirt); lower keeps only the clear, dark lines.", slider(page, "scan_ink", 50, "Lines", lambda: changed(page)))
