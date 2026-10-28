"""Setting file: accent colour."""
from ...theme import DEFAULT_ACCENT
from ...widgets import Swatches
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    def swatches(parent):
        sw = Swatches(ctx, parent, ctx.cfg.get("accent", DEFAULT_ACCENT), lambda v: page.set("accent", v, "look"), page.custom_color)
        page.setters["accent"] = lambda: (setattr(sw, "value", ctx.cfg.get("accent", DEFAULT_ACCENT)), sw.paint()); return sw
    return D("Appearance", "Accent colour", "Colour of buttons, selections and highlights.", swatches)
