"""The Logisim workspace: circuit view, JSON box and truth table side by side."""
import tkinter as tk

from vibesimulation.ui.window.pane_workspace import PaneWorkspace
from vibesimulation.workspaces.logisim.circuit.circuit_tabs import CircuitTabs
from vibesimulation.workspaces.logisim.circuit.circuit_view import CircuitView
from vibesimulation.workspaces.logisim.json_view.json_box import JsonView
from vibesimulation.workspaces.logisim.truth_table.truth_table import TableView
class WorkspacePage(PaneWorkspace):
    KEY, NAMES, DEFAULT = "logisim", {"circuit": "Circuit", "json": "Circuit JSON", "table": "Truth table"}, ["circuit", "json", "table"]

    def make_views(self, ctx, doc):
        return {"circuit": CircuitView(ctx, doc, self), "json": JsonView(ctx, doc, self), "table": TableView(ctx, doc, self)}

    def make_header(self, ctx, doc):
        return CircuitTabs(ctx, self, doc, self.views["circuit"])

    def on_page(self, name):
        """The IC view belongs to Logisim: it is hidden while another workspace (Multisim, Verilog ...) is shown and returns with Logisim."""
        win = getattr(self, "_ic_window", None)
        try:
            if win is None or not win.winfo_exists(): return
            if name == "logisim":
                if getattr(win, "_hidden_by_page", False): win.deiconify(); win._hidden_by_page = False
            elif win.state() != "withdrawn": win.withdraw(); win._hidden_by_page = True
        except tk.TclError: pass

    def __init__(self, ctx, master, shell):
        super().__init__(ctx, master, shell, shell.doc)
