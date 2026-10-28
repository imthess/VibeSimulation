"""Setting file: font."""
from tkinter import font as tkfont

from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    fams = ["Auto"] + sorted({f for f in tkfont.families(ctx.root) if not f.startswith("@")}, key=str.lower)
    return D("Appearance", "Font", "Typeface used throughout the app.", page.combo("font", "Auto", fams, after="look", width=22))
