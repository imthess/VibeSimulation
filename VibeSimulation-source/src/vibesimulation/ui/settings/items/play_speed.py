"""Setting file: play speed."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("Logisim", "Play speed", "Time each truth-table row stays on the circuit when you press Play.", page.seg("play_secs", [(f"{x} s", x) for x in (1, 2, 3, 5)], 2, int))
