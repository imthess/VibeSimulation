"""Setting file: remember window."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("General", "Remember window size and position", "Reopen the window where you left it.", page.switch("remember_window", True))
