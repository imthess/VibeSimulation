"""The top-bar menus of the VLSI page (each builder fills a tk menu `m` for the shell `sh`)."""
from ...core import commands as C
from ..menus import _Var, help_menu, item, view_menu


def _page(sh): return sh.pages["vlsi"]
def _cv(sh): return _page(sh).views["circuit"]


def file_menu(sh, m):
    a = sh.vactions
    item(sh, m, "New blank module", lambda: (a.new(), sh.show("vlsi")), "New blank circuit")
    m.add_command(label="Open Verilog file (.v)…", command=lambda: a.verilog_open() and sh.show("vlsi"))
    m.add_command(label="Save Verilog…", accelerator="Ctrl+S", command=a.verilog_save)
    m.add_separator()
    m.add_command(label="Open Logisim file (.circ)…", command=lambda: a.circ_open() and sh.show("vlsi"))
    m.add_command(label="Open image (AI import)…", command=sh.open_image)
    ex = sh.ctx.menu(); export_menu(sh, ex); m.add_cascade(label="Export", menu=ex)
    m.add_separator()
    item(sh, m, "Exit", sh.close, "Exit")


def export_menu(sh, m):
    a = sh.vactions
    m.add_command(label="Verilog (.v)", command=a.verilog_save)
    m.add_command(label="Logisim circuit (.circ)", command=a.circ)
    m.add_command(label="PDF  (circuit image + truth table)", command=a.pdf)
    m.add_command(label="Truth table (.csv)", command=a.csv)


def edit_menu(sh, m):
    item(sh, m, "Undo", sh.undo, "Undo"); item(sh, m, "Redo", sh.redo, "Redo")
    m.add_separator()
    m.add_command(label="Put all parts back in automatic places", command=lambda: _cv(sh).run(C.ClearPositions()))


def simulate_menu(sh, m):
    cv = _cv(sh); d = sh.vdoc; seq = d.has_seq(); st = "normal" if seq else "disabled"
    m.add_command(label="Reset simulation", accelerator="Ctrl+R", command=cv.reset_sim)
    m.add_command(label="Tick half cycle", accelerator="Ctrl+T", command=lambda: d.tick(1), state=st)
    m.add_command(label="Tick full cycle", accelerator="Ctrl+Shift+T", command=lambda: d.tick(2), state=st)
    m.add_checkbutton(label="Ticks enabled", accelerator="Ctrl+K", command=cv.toggle_auto, state=st, onvalue=True, offvalue=False, variable=_Var(sh, bool(cv._auto)))
    m.add_separator()
    m.add_command(label="Play the truth table", command=lambda: (sh.show("vlsi"), _page(sh).views["table"].toggle_play()))
    if not seq: m.add_command(label="(no clock or flip-flop in this circuit: ticks are off)", state="disabled")


def menus_for(sh):
    return [("File", lambda m: file_menu(sh, m)), ("Edit", lambda m: edit_menu(sh, m)), ("Simulate", lambda m: simulate_menu(sh, m)),
            ("View", lambda m: view_menu(sh, m)), ("Help", lambda m: help_menu(sh, m))]
