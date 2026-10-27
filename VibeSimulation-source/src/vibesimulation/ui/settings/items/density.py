"""Setting file: density."""
from ...theme import DENSITY
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Density", "How much space there is around controls.", page.seg("density", [(d, d) for d in DENSITY], "Comfortable", after="look"))
