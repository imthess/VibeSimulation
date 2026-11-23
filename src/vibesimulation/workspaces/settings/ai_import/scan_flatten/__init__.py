"""Setting: flatten shadows and uneven light."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Flatten shadows", "Remove shadows, folds and uneven light so the page is evenly white.", page.switch("scan_flatten", True, lambda: changed(page)))
