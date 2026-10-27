"""Setting file: corner style."""
from ...theme import RADII
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Corner style", "Sharp, softly rounded, or pill-shaped buttons.", page.seg("corners", [(r, r) for r in RADII], "Rounded", after="look"))
