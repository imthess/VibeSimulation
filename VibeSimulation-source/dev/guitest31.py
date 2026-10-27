import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import json, tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
j = {"inputs": ["A", "B"], "outputs": ["Y"], "gates": [
 {"id": "g1", "type": "AND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["n1"], "out": "n2"}, {"id": "g3", "type": "OR", "in": ["n2", "B"], "out": "Y"}]}
d.load_text(json.dumps(j)); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
v.select_all(); print("sel", sorted(v.sels))
v.select("g1"); v.toggle("g2"); print("sel", sorted(v.sels)); assert v.sels == {"g1", "g2"}
assert v.copy(); v.paste(); root.update()
print(d.valid, d.errors, d.layout_error, [c.id for c in d.circuit.components], [c.ins for c in d.circuit.components])
assert len(d.circuit.components) == 5 and d.valid
# the pasted AND/NOT pair is wired like the original (internal signal renamed), fed from A and B
comps = {c.id: c for c in d.circuit.components}
new = [c for c in d.circuit.components if c.id not in ("g1", "g2", "g3")]
a = next(c for c in new if c.type_name == "AND"); n = next(c for c in new if c.type_name == "NOT")
assert a.ins == {"In1": "A", "In2": "B"} and n.ins["In1"] == a.outs["Out"] and a.outs["Out"] != "n1", (a.ins, a.outs, n.ins)
# group move
v.sels = {a.id, n.id}; root.update()
pl = {p.comp.id: p for p in d.layout.parts}
class G(dict): pass
g = {"dx": 0, "dy": 60, "ok": True, "pls": [pl[a.id], pl[n.id]]}
v._drop_group(None, g); root.update(); print("moved", d.valid, [ (c.id, c.pos) for c in d.circuit.components if c.id in (a.id, n.id)])
v.sels = {a.id, n.id}; v.delete_selected(); root.update(); print(d.valid, [c.id for c in d.circuit.components], d.errors)
d.undo(); root.update(); print("undo", len(d.circuit.components))
# band
v.sels = set(); xs = [p.x for p in d.layout.parts]; 
ox, oy = v.org; s = v.scale
class E: pass
e0 = E(); e0.x, e0.y = ox - 5, oy - 5; e1 = E(); e1.x, e1.y = ox + 5000 * s, oy + 5000 * s
v._drop_band(e1, {"x": e0.x, "y": e0.y}); print("band", len(v.sels))
os.system("import -display :97 -window root /tmp/pv/multi.png")
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
