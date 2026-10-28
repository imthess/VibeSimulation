"""Multisim (analog) workspace: schematic, JSON and DC results panes."""
from ..pane_workspace import PaneWorkspace
from .json_box import AnalogJsonView
from .results_view import ResultsView
from .schematic_view import SchematicView


class MultisimPage(PaneWorkspace):
    KEY = "multisim"
    NAMES = {"schematic": "Schematic", "json": "Circuit JSON", "results": "DC results"}
    DEFAULT = ["schematic", "json", "results"]

    def make_views(self, ctx, doc):
        return {"schematic": SchematicView(ctx, doc, self), "json": AnalogJsonView(ctx, doc, self), "results": ResultsView(ctx, doc, self)}

    def __init__(self, ctx, master, shell):
        super().__init__(ctx, master, shell, shell.adoc)
        self.views["results"].page = self; self._hid = False

    def give_room(self, on):
        """Plots need space: while an analysis other than the operating point is shown, the JSON pane steps aside (View menu brings it back)."""
        if on and "json" not in self.hidden: self._hid = True; self.hidden.add("json"); self.layout()
        elif not on and self._hid: self._hid = False; self.hidden.discard("json"); self.layout()
