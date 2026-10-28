"""Entry point used by the installed `vibesimulation` command."""
from .components import load_all


def main():
    load_all()
    from .ui.main_window import main as run
    run()
