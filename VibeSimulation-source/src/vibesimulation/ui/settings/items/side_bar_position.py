"""Setting file: side bar position."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Activity bar position", "Show the bar on the left or the right.", page.seg("rail_side", [(x, x) for x in ("Left", "Right")], "Left", after="look"))
