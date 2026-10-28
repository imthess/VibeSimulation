import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ai.prompt import build_prompt
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
assert "ANALOG CIRCUIT" in build_prompt() and '"kind":"digital"' in build_prompt()
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.show("import"); root.update(); v = w.pages["import"].view
def state(): return (v.btn_logisim.on, v.btn_multisim.on, v.result_kind)
print("start", state())
# clicking a disabled button must do nothing
pass
digital = 'Here: ```json\n{"kind":"digital","inputs":["A","B"],"outputs":["Y"],"gates":[{"id":"g1","type":"NAND","in":["A","B"],"out":"Y"}]}\n```'
analog = '{"kind":"analog","title":"Divider","components":[{"id":"V1","type":"VoltageSource","value":"5","nodes":["n1","0"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["n1","n2"]},{"id":"R2","type":"Resistor","value":"1k","nodes":["n2","0"]}]}'
analog_nokind = '{"components":[{"id":"R1","type":"Resistor","value":"1k","nodes":["n1","0"]},{"id":"V1","type":"VoltageSource","value":"5","nodes":["n1","0"]}]}'
bad = '{"kind":"analog","components":[{"id":"R1","type":"Resistor","value":"1k","nodes":["n1","n2"]},{"id":"V1","type":"VoltageSource","value":"5","nodes":["n1","0"]}]}'
for name, ans in (("digital", digital), ("analog", analog), ("analog w/o kind", analog_nokind), ("analog dangling", bad), ("garbage", "no json here")):
    v.set_result(None); v.finish(ans); root.update(); print(name, state(), "|", v.status.t.get("1.0", "end").strip()[:90])
v.finish(analog); root.update()
os.system(f"import -display :97 -window root {S}imp.png")
v.btn_logisim.cmd() if v.result_kind == "digital" else None; print("after logisim click (should stay):", w.current)
v.btn_multisim.cmd(); root.update(); print("after multisim click:", w.current, "| adoc valid:", w.adoc.valid)
w.show("import"); v.finish(digital); v.btn_logisim.cmd(); root.update(); print("digital click:", w.current, "| doc valid:", w.doc.valid)
ctx.cfg.clear(); ctx.save_cfg()
