"""The SystemVerilog tab: rail entry, editor, compile on typing, circuit, testbench run, explorer, examples, Ctrl+6, recovery."""
import sys, os, time, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from pathlib import Path
import vibesimulation.product.recovery as RC
RC.PATH = Path(tempfile.mkdtemp()) / "rec.json"
from vibesimulation.product.recovery import Recovery
Recovery.__init__.__defaults__ = (RC.PATH,)
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.rail import ITEMS
from vibesimulation.product.examples import for_section
from vibesimulation.ui.product.gallery import open_example
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=6):
    for _ in range(n): root.update(); time.sleep(0.02)
w.ctx.toaster.show = lambda *a, **k: None; w.ctx.say = lambda *a, **k: None
chk("rail has a SystemVerilog item with Ctrl+6", any(i[0] == "systemverilog" and i[3] == "Ctrl+6" for i in ITEMS))
w.show("systemverilog"); pump()
pg = w.pages["systemverilog"]; ed = pg.views["verilog"]
chk("page is shown with its own title", w.current == "systemverilog" and ed.title == "SystemVerilog")
chk("the sample compiled in its own document", w.sdoc.valid and w.sdoc.cur == "traffic" and w.vdoc.cur != "traffic")
chk("editor shows the SystemVerilog text", "typedef enum" in ed.get_text())
chk("explorer lists the module and snippets", w.side.show_for("systemverilog") and any(k == "template" for k, _ in w.side.view().items.values()) and any(v == ("module", "traffic") for v in w.side.view().items.values()))
# typing: the circuit follows
ed.show_text("module t (input logic [3:0] a, output logic [3:0] y);\n  always_comb y = a + 4'd1;\nendmodule\n"); ed.flush_text(ed.get_text()); pump()
chk("typed SystemVerilog compiles and the circuit follows", w.sdoc.valid and w.sdoc.cur == "t" and len(w.sdoc.circuit.inputs) == 1)
chk("the VLSI document is untouched", w.vdoc.cur != "t")
ed.show_text("module t (input logic a, output logic y);\n  always_comb y = a;\n  assign y = ;\nendmodule\n"); ed.flush_text(ed.get_text()); pump()
chk("a mistake is shown on its line and keeps the circuit", w.sdoc.problems and w.sdoc.problems[0][1] == 3 and w.sdoc.cur == "t")
ed.show_text("interface bus; endinterface\n"); ed.flush_text(ed.get_text()); pump()
chk("an unsupported construct is explained", any("interface" in m for _, _, m in w.sdoc.problems))
# examples through the gallery loader
for e in for_section("systemverilog"):
    open_example(w, e); pump(); chk(f"example {e.key} opens and compiles", w.current == "systemverilog" and w.sdoc.valid)
    if e.testbench:
        w.pages["systemverilog"].dock.run(); pump()
        chk("its testbench runs from the dock", w.sdoc.last_run is not None and w.sdoc.last_run.error is None and w.sdoc.last_run.finished)
# keyboard
w.show("home"); pump(); root.event_generate("<Control-Key-6>"); pump(); chk("Ctrl+6 opens the page", w.current == "systemverilog")
# actions and menus
m = tk.Menu(root); from vibesimulation.ui.vlsi import menus as VM
VM.file_menu(w, m); labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) in ("command", "cascade")]
chk("File menu speaks of SystemVerilog", any("SystemVerilog file (.sv)" in l for l in labels))
out = tempfile.mkdtemp() + "/x.sv"; w.sactions._save = lambda title, ext, name, text: (open(out, "w").write(text), out)[1]
w.sactions.verilog_save(); chk("Save writes a .sv with the typed text", os.path.exists(out) and "module" in open(out).read())
# recovery
from vibesimulation.product import recovery as R
data = R.collect(w); chk("recovery keeps the SystemVerilog section", data["systemverilog"]["verilog"].strip() != "")
w.sdoc.new_blank("module z (input logic a, output logic y);\n  assign y = ~a;\nendmodule\n"); R.Recovery.restore(w, data); pump()
chk("restore puts it back", w.sdoc.valid and w.sdoc.cur != "z")
# commands
names = [c.title for c in w.commands]; chk("palette lists SystemVerilog commands", any("SystemVerilog workspace" in n for n in names) and any("Open SystemVerilog file" in n for n in names))
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
