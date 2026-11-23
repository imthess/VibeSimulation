"""Setting: scan every picture on import (crop, flatten shadows, black on white, about 1200 px)."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Scan pictures on import", "Cut away everything around the circuit, flatten shadows, make the paper white and the lines dark and shrink the picture before it is sent. The Import page has a Scanned / Original switch to see and change what is sent.",
             page.switch("scan_on", True, lambda: changed(page)))
