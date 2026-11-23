"""Setting: pane layout."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("General", "Pane layout", "Put the circuit, JSON and truth table panes back in their default places.", page.button("Reset layout", lambda: sh.active().reset()))
