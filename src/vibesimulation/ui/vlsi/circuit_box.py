"""VLSI pane 2: the circuit the Verilog describes.

It is the Logisim circuit drawing (click an input to toggle it, zoom, pan, clock controls) with one rule added: the *logic* is
written in Verilog, so a change that would alter the logic (add, delete or rewire something) is refused with a hint to edit the
Verilog. Layout changes (moving parts, wire routes, turning a part) are allowed and kept, because they are not part of the Verilog.
"""
from ...core import commands as C
from ..logisim.circuit_view import CircuitView

# commands that only change how the circuit is drawn
LAYOUT_ONLY = (C.MovePart, C.MoveParts, C.MovePin, C.ClearPositions, C.SetWire, C.RotatePart)


def is_layout_only(cmd):
    if isinstance(cmd, C.Batch): return all(is_layout_only(c) for c in cmd.cmds)
    return isinstance(cmd, LAYOUT_ONLY)


class VlsiCircuitView(CircuitView):
    number, title, hint = None, "Circuit", "click an input to toggle it; the circuit is built from the Verilog"

    on_pick = None                       # set by the page: called with the ids of the parts the user selected
    _quiet = False

    def highlight(self, ids):
        """Select the parts (without telling the page: this is the answer to a click in the Verilog)."""
        have = {c.id for c in self.doc.circuit.components} if self.doc.valid else set(); ids = {i for i in ids if i in have}
        self._quiet = True
        try:
            self.sels = set(ids); self.sel = next(iter(ids)) if len(ids) == 1 else None; self.wsel = set(); self.draw()
        finally: self._quiet = False

    def select(self, cid):
        super().select(cid)
        if self.on_pick and not self._quiet and cid: self.on_pick({cid})

    def toggle(self, cid):
        super().toggle(cid)
        if self.on_pick and not self._quiet and self.sels: self.on_pick(set(self.sels))

    def run(self, cmd):
        if not is_layout_only(cmd):
            self.status.configure(text="The circuit is written in Verilog: change it there (the Verilog box).")
            return
        super().run(cmd)

    def menu_here(self, e):
        """Right-click on empty space: nothing can be added here, only the view can be reset."""
        m = self.ctx.menu()
        m.add_command(label="Show the whole circuit", command=self.fit)
        m.add_command(label="Put all parts back in automatic places", command=lambda: self.run(C.ClearPositions()))
        m.tk_popup(e.x_root, e.y_root)

    def parts(self, at=None):
        self.status.configure(text="The circuit is written in Verilog: add parts there (a library part is `vs_<Type>`).")

    def download(self):
        """The .circ download works on this page's own document."""
        if self.main is not None and hasattr(self.main, "vactions"): return self.main.vactions.circ()
