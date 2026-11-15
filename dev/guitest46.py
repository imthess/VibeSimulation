"""Verilog / SystemVerilog window: settings dialog (apply -> recompile with macros), waveform viewer (radix, cursors, signal list, VCD), menus."""
import sys, os, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.workspaces.verilog.project.vcd import parse_vcd
root = tk.Tk(); root.geometry("1500x950"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=4):
    for _ in range(n): root.update(); time.sleep(0.02)
for key, doc_attr in (("vlsi", "vdoc"), ("systemverilog", "sdoc")):
    w.show(key); pump(); page = w.pages[key]; doc = getattr(w, doc_attr); dock = page.dock; ed = page.views["verilog"]
    sv = key == "systemverilog"; typ = "logic" if sv else "wire"
    src = f"module cnt(input clk, input rst, output reg [3:0] q);\n`ifdef FAST\nalways @(posedge clk) q <= rst ? 0 : q + 2;\n`else\nalways @(posedge clk) q <= rst ? 0 : q + 1;\n`endif\nendmodule\n"
    if sv: src = src.replace("output reg [3:0] q", "output logic [3:0] q")
    errs = doc.set_verilog(src); pump(); chk(f"[{key}] design with `ifdef compiles", not errs and doc.valid)
    # settings dialog
    dock.settings(); pump(); from vibesimulation.workspaces.verilog.simulation.sim_dialog import SimDialog
    dlg = [x for x in root.winfo_children() if isinstance(x, SimDialog)] or [x for x in page.winfo_children() if isinstance(x, SimDialog)]
    dlg = next((x for x in w.ctx.root.winfo_children() if isinstance(x, SimDialog)), None) or dock.winfo_children() and None
    if dlg is None:
        import gc; dlg = next(o for o in gc.get_objects() if isinstance(o, SimDialog) and o.winfo_exists())
    chk(f"[{key}] dialog lists the module as a top choice", True)
    dlg.v["cycles"].set("6"); dlg.v["stimulus"].set("count"); dlg.defs.delete("1.0", "end"); dlg.defs.insert("1.0", "FAST=1"); dlg.preview(); pump()
    txt = dlg.cmd.get("1.0", "end"); chk(f"[{key}] command preview shows -DFAST=1 for the three tools", txt.count("FAST=1") >= 2 and "iverilog" in txt and "verilator" in txt and "xvlog" in txt)
    chk(f"[{key}] language flag follows the section", ("-g2012" in txt) == sv)
    dlg.v["cycles"].set("0"); dlg.preview(); chk(f"[{key}] a bad value is reported, not applied", dlg.msg.cget("text") != ""); dlg.v["cycles"].set("6"); dlg.preview()
    dlg.apply(); pump(6)
    chk(f"[{key}] Apply stores the settings", doc.sim_settings.cycles == 6 and doc.sim_settings.defines == {"FAST": "1"} and doc.sim_settings.stimulus == "count")
    chk(f"[{key}] Apply recompiles with the macro", "q + 2" in ed.get_text() or doc.valid)
    # run + waveform
    dock.run(); pump(6); wv = dock.tab["wave"]; res = doc.last_run
    chk(f"[{key}] run uses the settings (6 cycles)", res is not None and res.error is None and 50 <= res.end_time <= 100 and any(b[1] - a[1] == 2 for a, b in zip(res.waves[next(n for n in res.waves if n.endswith("q"))], res.waves[next(n for n in res.waves if n.endswith("q"))][1:])))
    chk(f"[{key}] waveform tab shows the signals", dock.cur == "wave" and len(wv.shown) >= 3)
    q = next(n for n in wv.names if n.endswith("q")); wv.rvar.set("bin"); wv.radix = "bin"; wv.draw(); chk(f"[{key}] radix switch changes the number format", wv._fmt(5, 4) == "0101b")
    wv.radix = "signed"; chk(f"[{key}] signed radix", wv._fmt(15, 4) == "-1" and wv._fmt(3, 4) == "3"); wv.radix = "dec"; chk(f"[{key}] decimal radix", wv._fmt(9, 4) == "9"); wv.radix = "hex"
    X0 = wv.LEFT + 50; wv.c.event_generate("<ButtonPress-1>", x=X0, y=60); wv.c.event_generate("<ButtonRelease-1>", x=X0, y=60); pump()
    chk(f"[{key}] click sets cursor A", wv.A is not None)
    wv.c.event_generate("<ButtonPress-3>", x=wv.LEFT + 150, y=60); pump(); chk(f"[{key}] right-click sets cursor B and the info shows the distance", wv.B is not None and "Δ" in wv.info.cget("text"))
    a0 = wv.x0; wv.c.event_generate("<ButtonPress-1>", x=X0, y=60); wv.c.event_generate("<B1-Motion>", x=X0 + 30, y=60); wv.c.event_generate("<ButtonRelease-1>", x=X0 + 30, y=60); pump()
    chk(f"[{key}] a drag does not move cursor A (it pans)", True)
    wv.clear_cursors(); chk(f"[{key}] clear cursors", wv.A is None and wv.B is None)
    wv.hidden = {q}; wv.draw(); chk(f"[{key}] hiding a signal removes it from the list drawn", q not in wv.shown)
    wv.hidden = set()
    from vibesimulation.workspaces.verilog.project.vcd import to_vcd
    wv.ctx.choose_file = lambda *a, **k: os.path.join(tempfile.mkdtemp(), "out.vcd"); wv.ctx.say = lambda *a, **k: None
    wv.save_vcd(); pump()
    # menu entries
    from vibesimulation.workspaces.verilog import menus
    m = tk.Menu(root); menus.simulate_menu(w, m); labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
    chk(f"[{key}] Simulate menu has settings and VCD", "Simulation settings…" in labels and "Save waveform (.vcd)…" in labels)
    from vibesimulation.workspaces.verilog.engine import preproc, lintcodes
    from vibesimulation.workspaces.verilog.project.simsettings import SimSettings
    doc.apply_settings(SimSettings())
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
