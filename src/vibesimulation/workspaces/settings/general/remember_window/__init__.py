"""Setting: remember window."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("General", "Remember window size and position", "Reopen the window where you left it.", page.switch("remember_window", True))
