"""Setting: grid."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("Logisim", "Show dotted grid behind the circuit", "", page.switch("grid", True, sh.apply_settings))
