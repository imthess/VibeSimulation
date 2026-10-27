"""Setting file: show intermediate."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Logisim", "Show intermediate signals in the truth table", "Also list the values of the wires between gates.", page.switch("show_mid", True, sh.apply_settings))
