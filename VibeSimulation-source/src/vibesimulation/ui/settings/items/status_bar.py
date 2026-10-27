"""Setting file: status bar."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Show status bar", "The slim bar at the bottom with shortcut hints.", page.switch("show_status", True))
