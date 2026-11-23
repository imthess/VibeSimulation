"""Small calls from Settings into the Import page (kept in one place so the settings do not need to know the page's internals)."""


def changed(page):
    """A scan setting changed: the Import page rebuilds what will be sent."""
    page.ctx.save_cfg()
    try: page.shell.pages["import"].view.scan_changed()
    except Exception: pass
