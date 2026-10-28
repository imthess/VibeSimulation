"""Setting file: recent files."""
from ..item import D


def item(page):
    ctx, sh = page.ctx, page.shell
    return D("General", "Recent files", "Forget the list shown on Home and in File > Open Recent.", page.button("Clear list", lambda: (ctx.cfg.__setitem__("recent", []), ctx.save_cfg(), ctx.toast("Recent files cleared"))))
