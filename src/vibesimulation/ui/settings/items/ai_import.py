"""Setting file: ai import."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("AI & Import", "AI import", "Open the page where you insert a picture and choose the model.", page.button("Open Import & AI", lambda: sh.show("import"), "primary"))
