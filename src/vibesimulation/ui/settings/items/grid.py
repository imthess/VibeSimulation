"""Setting file: grid."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Logisim", "Show dotted grid behind the circuit", "", page.switch("grid", True, sh.apply_settings))
