"""Setting file: side bar size."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Activity bar size", "Width of the bar and size of its icons.", page.seg("rail_size", [(x, x) for x in ("Small", "Medium", "Large")], "Small", after="look"))
