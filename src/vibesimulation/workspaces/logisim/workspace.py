"""The Logisim workspace: circuit view, JSON box and truth table side by side."""
from ...ui.pane_workspace import PaneWorkspace
from .circuit.circuit_view import CircuitView
from .json_view.json_box import JsonView
from .truth_table.truth_table import TableView


class WorkspacePage(PaneWorkspace):
    KEY, NAMES, DEFAULT = "logisim", {"circuit": "Circuit", "json": "Circuit JSON", "table": "Truth table"}, ["circuit", "json", "table"]

    def make_views(self, ctx, doc):
        return {"circuit": CircuitView(ctx, doc, self), "json": JsonView(ctx, doc, self), "table": TableView(ctx, doc, self)}

    def __init__(self, ctx, master, shell):
        super().__init__(ctx, master, shell, shell.doc)
