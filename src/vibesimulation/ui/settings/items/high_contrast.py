"""Setting file: high contrast."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "High contrast", "Stronger text and border contrast.", page.switch("high_contrast", False, "look"))
