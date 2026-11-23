"""Setting: crop to the circuit and how much margin to keep."""
from vibesimulation.workspaces.ai_import.ui_hooks import changed
from vibesimulation.workspaces.settings.ai_import.controls import slider
from vibesimulation.workspaces.settings.item import D
def item(page):
    sw = page.switch("scan_crop", True, lambda: changed(page)); sl = slider(page, "scan_margin", 4, "Margin", lambda: changed(page))
    def make(parent):
        import tkinter as tk
        f = tk.Frame(parent, bd=0, bg=parent.cget("bg")); sw(f).pack(side="left", padx=(0, 14)); sl(f).pack(side="left"); return f
    return D("AI & Import", "Crop to the circuit (and margin)", "Automatically cut away the table, the rest of the page and other notes around the drawing. The slider keeps a margin (in % of the drawing). You can also drag the crop box yourself on the Import page.", make)
