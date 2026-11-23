"""Setting: models."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    sh = page.shell
    return D("AI & Import", "AI import", "Open the page where you insert a picture and choose the model.", page.button("Open Import & AI", lambda: sh.show("import"), "primary"))
