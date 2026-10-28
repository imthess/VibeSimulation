"""Setting file: reset appearance."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Reset appearance", "Back to theme System, Blue, Rounded, Comfortable, 100%.", page.button("Reset", sh.reset_look))
