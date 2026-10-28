"""Setting file: reduce motion."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Reduce motion", "Turn off hover fades and switch animations.", page.switch("reduce_motion", False, "look"))
