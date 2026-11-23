"""Setting: recent files."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    ctx = page.ctx
    return D("General", "Recent files", "Forget the list shown on Home and in File > Open Recent.", page.button("Clear list", lambda: (ctx.cfg.__setitem__("recent", []), ctx.save_cfg(), ctx.toast("Recent files cleared"))))
