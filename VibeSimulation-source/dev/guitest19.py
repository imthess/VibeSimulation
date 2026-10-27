import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.export.logisim import to_circ
from vibesimulation.core.serializer import parse
from vibesimulation.analog.netlist import parse as aparse, to_spice
from vibesimulation.analog.document import SAMPLE
from vibesimulation.ui.main_window import MainWindow
from randtest import rand_circuit
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
rng = random.Random(5); c = None
while c is None or len(c.components) < 3: c = rand_circuit(rng)
open("/tmp/t_logic.circ", "w").write(to_circ(c)); open("/tmp/t_div.cir", "w").write(to_spice(aparse(SAMPLE)[0])); open("/tmp/t_x.ms14", "wb").write(b"PK\x03\x04junk")
open("/tmp/t_bad.circ", "w").write("<project><circuit name='main'><comp lib='1' loc='(100,100)' name='AND Gate'/></circuit></project>")
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx; w.show("import"); root.update(); v = w.pages["import"].view
def pick(path): ctx.choose_file = lambda *a, **k: path
def st(): return v.status.t.get("1.0", "end").strip().replace("\n", " | ")[:260]
for label, which, path in (("logic circ", "logisim", "/tmp/t_logic.circ"), ("spice", "multisim", "/tmp/t_div.cir"), ("ms14", "multisim", "/tmp/t_x.ms14"), ("bad circ", "logisim", "/tmp/t_bad.circ")):
    pick(path); v.set_result(None); v.open_circuit_file(which); root.update()
    print(label, (v.btn_logisim.on, v.btn_multisim.on), "|", st())
pick("/tmp/t_logic.circ"); v.open_circuit_file("logisim"); root.update()
print("table rows:", len(w.pages["logisim"].views["table"].tree.get_children()), "doc valid", w.doc.valid)
os.system(f"import -display :97 -window root {S}imp2.png")
v.btn_logisim.cmd(); root.update(); print("page:", w.current)
w.show("import"); pick("/tmp/t_div.cir"); v.open_circuit_file("multisim"); v.btn_multisim.cmd(); root.update(); print("page:", w.current, "adoc valid", w.adoc.valid)
ctx.cfg.clear(); ctx.save_cfg()
