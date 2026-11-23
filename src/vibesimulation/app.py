"""Entry point used by the installed `vibesimulation` command."""
from vibesimulation.workspaces.logisim.components import load_all
def main():
    load_all()
    from vibesimulation.ui.window.main_window import main as run
    run()
