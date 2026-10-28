"""Setting file: pane layout."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("General", "Pane layout", "Put the circuit, JSON and truth table panes back in their default places.", page.button("Reset layout", lambda: sh.active().reset()))
