"""The contents of the top menus. Each builder fills a tk menu `m` for the shell `sh`; menus_for() says which menus a page gets and in which order."""
import os

from .multisim.parts_bin import fill_place_menu


def _acc(sh, title): return sh.menubar.acc(title) if hasattr(sh, "menubar") else ""


def item(sh, m, label, fn, title=None, **kw):
    m.add_command(label=label, command=fn, accelerator=_acc(sh, title or ""), **kw)


def _lg(sh): return sh.pages["logisim"].views["circuit"]
def _sv(sh): return sh.pages["multisim"].views["schematic"]
def _rv(sh): return sh.pages["multisim"].views["results"]


def menus_for(sh, page):
    common_end = [("View", lambda m: view_menu(sh, m)), ("Help", lambda m: help_menu(sh, m))]
    if page == "logisim":
        return [("File", lambda m: file_menu(sh, m)), ("Edit", lambda m: edit_logisim(sh, m)), ("Project", lambda m: project_menu(sh, m)),
                ("Simulate", lambda m: simulate_logisim(sh, m))] + common_end
    if page in ("vlsi", "systemverilog"):
        from .vlsi.menus import menus_for as vlsi_menus            # the SystemVerilog page uses the same menus on its own document and actions
        return vlsi_menus(sh)
    if page == "multisim":
        return [("File", lambda m: file_menu(sh, m)), ("Edit", lambda m: edit_multisim(sh, m)), ("View", lambda m: view_menu(sh, m)), ("Place", lambda m: place_menu(sh, m)),
                ("Simulate", lambda m: simulate_multisim(sh, m)), ("Transfer", lambda m: export_menu(sh, m)), ("Tools", lambda m: tools_multisim(sh, m)), ("Help", lambda m: help_menu(sh, m))]
    return [("File", lambda m: file_menu(sh, m)), ("Edit", lambda m: edit_basic(sh, m))] + common_end


# ------------------------------------------------------------------ File
def file_menu(sh, m):
    a = sh.cur_actions; page = "multisim" if sh.analog() else "logisim"
    item(sh, m, "New blank circuit", lambda: (a.new(), sh.show(page)), "New blank circuit")
    item(sh, m, "Open circuit JSON…", lambda: a.json_open() and sh.show(page), "Open circuit JSON…")
    rec = sh.ctx.menu()
    items = [x for x in sh.ctx.cfg.get("recent", []) if os.path.isfile(x[0]) and x[0].lower().endswith((".json", ".txt"))][:10]
    for x in items: rec.add_command(label=os.path.basename(x[0]), command=lambda p=x[0]: a.json_open(p) and sh.show(page))
    if items:
        rec.add_separator(); rec.add_command(label="Clear list", command=lambda: (sh.ctx.cfg.__setitem__("recent", []), sh.ctx.save_cfg()))
    m.add_cascade(label="Open Recent", menu=rec, state="normal" if items else "disabled")
    m.add_separator()
    if sh.analog(): m.add_command(label="Open Logisim file (.circ)…", command=lambda: (sh.show("import"), sh.pages["import"].view.open_circuit_file("logisim")))
    else: m.add_command(label="Open Logisim file (.circ)…", command=lambda: a.circ_open() and sh.show(page))
    m.add_command(label="Open Multisim / SPICE file (.cir)…", command=lambda: (sh.show("import"), sh.pages["import"].view.open_circuit_file("multisim")))
    item(sh, m, "Open image (AI import)…", sh.open_image, "Open image (AI import)…")
    m.add_separator()
    item(sh, m, "Save circuit JSON…", a.json_save, "Save circuit JSON…")
    ex = sh.ctx.menu(); export_menu(sh, ex); m.add_cascade(label="Export", menu=ex)
    m.add_separator()
    pref = sh.ctx.menu()
    item(sh, pref, "Settings", lambda: sh.show("settings"), "Settings")
    item(sh, pref, "Keyboard shortcuts", sh.show_shortcuts, "Keyboard shortcuts")
    th = sh.ctx.menu()
    for mode, name in (("light", "Light"), ("dark", "Dark"), ("system", "Match system")): th.add_command(label=name + ("   ✓" if sh.ctx.mode == mode else ""), command=lambda mode=mode: sh.set_pref("mode", mode))
    pref.add_cascade(label="Theme", menu=th)
    m.add_cascade(label="Preferences", menu=pref)
    m.add_separator()
    item(sh, m, "Exit", sh.close, "Exit")


def export_menu(sh, m):
    s = sh; a, b = s.actions, s.aactions
    if s.analog():
        item(sh, m, "SPICE netlist (.cir)  - import into Multisim", b.cir, "Download circuit (.circ for Logisim / .cir for Multisim)")
        item(sh, m, "PDF  (schematic + results)", b.pdf, "Download PDF (circuit + truth table)")
        m.add_command(label="Circuit JSON (.json)", command=b.json_save); m.add_command(label="Results (.csv)", command=b.csv)
    else:
        item(sh, m, "Logisim circuit (.circ)", a.circ, "Download circuit (.circ for Logisim / .cir for Multisim)")
        item(sh, m, "PDF  (circuit image + truth table)", a.pdf, "Download PDF (circuit + truth table)")
        m.add_command(label="Circuit JSON (.json)", command=a.json_save); m.add_command(label="Truth table (.csv)", command=a.csv)


# ------------------------------------------------------------------ Edit
def _undo_redo(sh, m):
    item(sh, m, "Undo", sh.undo, "Undo"); item(sh, m, "Redo", sh.redo, "Redo")


def edit_basic(sh, m): _undo_redo(sh, m)


def edit_logisim(sh, m):
    cv = _lg(sh); _undo_redo(sh, m); m.add_separator()
    ok = sh.doc.valid; has = bool(cv.sels) and ok
    m.add_command(label="Cut", accelerator="Ctrl+X", command=cv.cut, state="normal" if has else "disabled")
    m.add_command(label="Copy", accelerator="Ctrl+C", command=cv.copy, state="normal" if has else "disabled")
    m.add_command(label="Paste", accelerator="Ctrl+V", command=cv.paste, state="normal" if getattr(sh.ctx, "clipboard_parts", None) and ok else "disabled")
    m.add_command(label="Delete", accelerator="Del", command=cv.delete_selected, state="normal" if (has or cv.wsel) else "disabled")
    m.add_command(label="Select all", accelerator="Ctrl+A", command=cv.select_all, state="normal" if ok else "disabled")
    m.add_separator()
    m.add_command(label="Turn clockwise", accelerator="R", command=lambda: cv.turn(1), state="normal" if cv.sel else "disabled")
    m.add_command(label="Turn counter-clockwise", accelerator="L", command=lambda: cv.turn(-1), state="normal" if cv.sel else "disabled")
    m.add_separator()
    from ..core import commands as C
    m.add_command(label="Put all parts back in automatic places", command=lambda: cv.run(C.ClearPositions()), state="normal" if ok else "disabled")


def edit_multisim(sh, m):
    sv = _sv(sh); _undo_redo(sh, m); m.add_separator()
    m.add_command(label="Delete", accelerator="Del", command=sv.delete_selected, state="normal" if (sv.sel or sv.wsel) else "disabled")
    m.add_command(label="Rename part…", command=lambda: sv.rename(sh.adoc.netlist.part(sv.sel)), state="normal" if sv.sel else "disabled")
    m.add_separator(); m.add_command(label="Put all parts back in automatic places", command=sv.tidy)


# ------------------------------------------------------------------ Logisim: Project, Simulate
def project_menu(sh, m):
    cv = _lg(sh); d = sh.doc
    m.add_command(label="Add circuit…", command=cv.new_circuit)
    m.add_command(label=f"Rename circuit '{d.cur}'…", command=lambda: cv.rename_circuit(d.cur))
    m.add_command(label=f"Remove circuit '{d.cur}'", command=lambda: cv.delete_circuit(d.cur), state="normal" if len(d.circuit_names()) > 1 else "disabled")
    sub = sh.ctx.menu()
    for n in d.circuit_names(): sub.add_command(label=n + ("   ✓" if n == d.cur else ""), command=lambda n=n: d.switch(n))
    m.add_cascade(label="Go to circuit", menu=sub)
    m.add_separator()
    m.add_command(label="Analyze circuit  (show the truth table)", command=lambda: show_pane(sh, "table"))
    m.add_command(label="Get circuit statistics…", command=lambda: circuit_stats(sh))
    m.add_separator()
    m.add_command(label="Options…", command=lambda: sh.show("settings"))


def show_pane(sh, key):
    w = sh.pages["logisim"]
    if key in w.hidden: w.toggle(key)
    sh.show("logisim")


def circuit_stats(sh):
    d = sh.doc
    if not d.valid or d.circuit is None: return sh.ctx.say("Circuit statistics", "The circuit has a problem right now: fix the JSON first.")
    c = d.circuit; counts = {}
    for p in c.components: counts[p.type_name] = counts.get(p.type_name, 0) + 1
    lines = [f"Circuit '{d.cur}'", f"  Input pins: {len(c.inputs)}", f"  Output pins: {len(c.outputs)}", f"  Parts: {len(c.components)}"] + [f"    {n}: {k}" for n, k in sorted(counts.items())]
    lines.append(f"  Signals: {len(c.signals())}")
    sh.ctx.say("Circuit statistics", "\n".join(lines))


def simulate_logisim(sh, m):
    cv = _lg(sh); d = sh.doc; seq = d.has_seq(); st = "normal" if seq else "disabled"
    m.add_command(label="Reset simulation", accelerator="Ctrl+R", command=cv.reset_sim)
    m.add_command(label="Tick half cycle", accelerator="Ctrl+T", command=lambda: d.tick(1), state=st)
    m.add_command(label="Tick full cycle", accelerator="Ctrl+Shift+T", command=lambda: d.tick(2), state=st)
    m.add_checkbutton(label="Ticks enabled", accelerator="Ctrl+K", command=cv.toggle_auto, state=st, onvalue=True, offvalue=False,
                      variable=_Var(sh, bool(cv._auto)))
    fq = sh.ctx.menu()
    for hz in (1, 2, 4, 8, 16, 32): fq.add_command(label=f"{hz} Hz" + ("   ✓" if cv.hz == hz else ""), command=lambda hz=hz: (setattr(cv, "hz", hz), cv.b_hz.configure(text=f"{hz} Hz")))
    m.add_cascade(label="Tick frequency", menu=fq, state=st)
    m.add_separator()
    m.add_command(label="Play the truth table", command=lambda: (show_pane(sh, "table"), sh.pages["logisim"].views["table"].toggle_play()))
    if not seq: m.add_command(label="(no clock or flip-flop in this circuit: ticks are off)", state="disabled")


def _Var(sh, v):
    import tkinter as tk
    var = tk.BooleanVar(master=sh.root, value=v); keep = sh.__dict__.setdefault("_menu_vars", []); keep.append(var); del keep[:-60]      # a menu does not keep its variable alive
    return var


# ------------------------------------------------------------------ Multisim: Place, Simulate, Tools
def place_menu(sh, m):
    sv = _sv(sh); fill_place_menu(m, sh.ctx, sv.place)


def simulate_multisim(sh, m):
    rv = _rv(sh)
    for key, name in rv.MODES.items():
        m.add_command(label=name + ("   ✓" if rv.mode == key else ""), command=lambda key=key: (sh.show("multisim"), rv.set_mode(key)))
    m.add_separator()
    m.add_command(label="Show results pane", command=lambda: _show_ms(sh, "results"))


def _show_ms(sh, key):
    w = sh.pages["multisim"]
    if key in w.hidden: w.toggle(key)
    sh.show("multisim")


def tools_multisim(sh, m):
    sv = _sv(sh)
    m.add_command(label="Put all parts back in automatic places", command=sv.tidy)
    m.add_separator()
    from .multisim.instruments import INSTRUMENTS, open_instrument
    for name in INSTRUMENTS: m.add_command(label=name + "…", command=lambda name=name: open_instrument(sh.ctx, sv.doc, name, sh.__dict__.setdefault("_instruments", {})))
    m.add_separator()
    m.add_command(label="Show the component database", command=lambda: sh.show_side(True))
    m.add_separator()
    m.add_command(label="Options…", command=lambda: sh.show("settings"))


# ------------------------------------------------------------------ View, Help
def view_menu(sh, m):
    w = sh.active() if sh.current in ("logisim", "multisim", "vlsi", "systemverilog") else None
    m.add_checkbutton(label="Explorer / component bar", accelerator="Ctrl+B", command=sh.toggle_side, variable=_Var(sh, sh.side_open()), onvalue=True, offvalue=False)
    if w is not None:
        m.add_separator()
        for key, name in w.NAMES.items():
            m.add_command(label=("✔  " if key not in w.hidden else "     ") + name, command=lambda k=key: w.toggle(k))
        m.add_command(label="Reset pane layout", command=w.reset)
    if sh.current in ("logisim", "vlsi", "systemverilog"):
        cv = sh.pages[sh.current].views["circuit"]; m.add_separator()
        m.add_command(label="Zoom in", command=lambda: cv.zoom_by(1.25)); m.add_command(label="Zoom out", command=lambda: cv.zoom_by(0.8)); m.add_command(label="Fit the whole circuit", command=cv.fit)
    m.add_separator()
    ap = sh.ctx.menu()
    item(sh, ap, "Dark / light mode", sh.toggle_dark, "Toggle dark / light mode")
    item(sh, ap, "Make text larger", lambda: sh.zoom(1), "Make text larger"); item(sh, ap, "Make text smaller", lambda: sh.zoom(-1), "Make text smaller")
    item(sh, ap, "Reset text size", lambda: sh.zoom(0), "Reset text size")
    m.add_cascade(label="Appearance", menu=ap)
    item(sh, m, "Full screen", sh.toggle_fullscreen, "Toggle full screen")
    m.add_separator()
    item(sh, m, "Command palette…", sh.open_palette, "Command palette")


def help_menu(sh, m):
    item(sh, m, "Keyboard shortcuts", sh.show_shortcuts, "Keyboard shortcuts")
    item(sh, m, "Command palette", sh.open_palette, "Command palette")
    m.add_separator()
    m.add_command(label="Go to Home", command=lambda: sh.show("home"))
    m.add_command(label="Examples gallery…", command=sh.show_gallery)
    m.add_command(label="About VibeSimulation…", command=sh.show_about)
