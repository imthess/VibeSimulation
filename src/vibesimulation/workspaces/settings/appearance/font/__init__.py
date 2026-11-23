"""Setting: font."""
from tkinter import font as tkfont

from vibesimulation.workspaces.settings.item import D
def item(page):
    ctx = page.ctx
    fams = ["Auto"] + sorted({f for f in tkfont.families(ctx.root) if not f.startswith("@")}, key=str.lower)
    return D("Appearance", "Font", "Typeface used throughout the app.", page.combo("font", "Auto", fams, after="look", width=22))
