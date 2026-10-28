"""The VLSI page: Verilog, Circuit and Truth table side by side (panes can be swapped and hidden like in the other pages)."""
from ..pane_workspace import PaneWorkspace
from .circuit_box import VlsiCircuitView
from .truth_table_box import VlsiTableView
from .dock import BottomDock
from .verilog_box import VerilogView


class VlsiPage(PaneWorkspace):
    KEY = "vlsi"
    NAMES = {"verilog": "Verilog", "circuit": "Circuit", "table": "Truth table"}
    DEFAULT = ["verilog", "circuit", "table"]
    EDITOR = "verilog"
    DOC = "vdoc"                         # the shell attribute holding this page's document (the SystemVerilog page uses "sdoc")
    EDITOR_VIEW = VerilogView

    def make_views(self, ctx, doc):
        return {"verilog": self.EDITOR_VIEW(ctx, doc, self), "circuit": VlsiCircuitView(ctx, doc, self), "table": VlsiTableView(ctx, doc, self)}

    def __init__(self, ctx, master, shell):
        self.dock = None
        super().__init__(ctx, master, shell, getattr(shell, self.DOC))
        self.dock = BottomDock(ctx, self, getattr(shell, self.DOC), self); self.layout()
        for v in self.views.values(): v.page = self
        self.views["circuit"].on_pick = self.pick_part

    def layout(self):
        super().layout()
        if self.dock is not None:
            self.dock.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(1, 0)); self.rowconfigure(2, weight=0)
            self.grid_propagate(True)

    # ---- Verilog line <-> circuit part
    def goto_line(self, line, in_tb=False):
        """Show the Verilog (or testbench) text at `line` and put the cursor there."""
        v = self.views["verilog"]; v.goto(line, tb=in_tb)
        if v.card.winfo_manager() == "": self.hidden.discard("verilog"); self.layout()

    def pick_part(self, ids):
        """A part was clicked in the circuit: show the line of the Verilog that made it."""
        lines = getattr(self.shell, self.DOC).part_lines(); ls = sorted({lines[i] for i in ids if i in lines})
        if ls: self.views["verilog"].goto(ls[0], tb=False, focus=False)

    def line_picked(self, line):
        """The cursor is on `line` of the Verilog: mark the parts it made in the circuit."""
        from ...vlsi.hints import parts_on_line
        self.views["circuit"].highlight(parts_on_line(getattr(self.shell, self.DOC).part_lines(), line))
