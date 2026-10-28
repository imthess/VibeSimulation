"""Setting file: text size."""
from ...theme import SCALES
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Text size", "Scales all text in the app  (Ctrl+=  /  Ctrl+-  /  Ctrl+0).", page.seg("text_scale", [(f"{s}%", s) for s in SCALES], 100, int, after="look"))
