"""Setting file: auto open."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("General", "Open the workspace after converting an image", "Jump straight to Logisim or Multisim when the AI import finishes (otherwise use the two buttons on the Import page).", page.switch("auto_open", False))
