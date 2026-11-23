"""Setting: reset appearance."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("Appearance", "Reset appearance", "Back to theme System, Blue, Rounded, Comfortable, 100%.", page.button("Reset", sh.reset_look))
