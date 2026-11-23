"""Setting: show intermediate."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("Logisim", "Show intermediate signals in the truth table", "Also list the values of the wires between gates.", page.switch("show_mid", True, sh.apply_settings))
