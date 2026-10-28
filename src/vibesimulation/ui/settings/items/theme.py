"""Setting file: theme."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Appearance", "Theme", "Light, dark, or follow your operating system.", page.seg("mode", (("Light", "light"), ("Dark", "dark"), ("System", "system")), "system", after="look"))
