"""Multisim box 2: the analog circuit JSON (same editor as Logisim's JSON box)."""
from ..logisim.json_box import JsonView


class AnalogJsonView(JsonView):
    number, title, hint = None, "Circuit JSON", "edit it: results update live"
    layout_prefix = "The circuit could not be solved: "

    def ok_kind(self, d): return "warn" if d.netlist.floating() else "ok"

    def ok_text(self, d):
        fl = d.netlist.floating()
        if fl:
            names = ", ".join(f"{p.id} terminal {k + 1}" for p, k in fl[:6]) + (f" and {len(fl) - 6} more" if len(fl) > 6 else "")
            return f"⚠ Incomplete circuit: not connected: {names}"
        return f"✔ Valid circuit: {len(d.netlist.parts)} parts, {len(d.netlist.nets())} nets (+ ground)"
