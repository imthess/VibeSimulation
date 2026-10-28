"""VS Code style shell: menus per page, side bar explorer / component database, Logisim placement tools, activity bar."""
import faulthandler; faulthandler.dump_traceback_later(40, exit=True)
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.analog import components as AC
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ctx = w.ctx; ok = True
ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=4):
    for _ in range(n): root.update(); time.sleep(0.02)
# 1. every menu of every page builds, with the expected names
want = {"logisim": ["File", "Edit", "Project", "Simulate", "View", "Help"], "multisim": ["File", "Edit", "View", "Place", "Simulate", "Transfer", "Tools", "Help"],
        "home": ["File", "Edit", "View", "Help"], "import": ["File", "Edit", "View", "Help"], "settings": ["File", "Edit", "View", "Help"]}
for pg, names in want.items():
    w.show(pg); pump()
    chk(f"{pg}: menus {names}", [b.name for b in w.menubar.buttons] == names)
    for b in w.menubar.buttons:
        m = ctx.menu()
        try: b.builder(m); n = len(m.items) if hasattr(m, "items") else 1
        except Exception as e: chk(f"{pg} menu {b.name} builds ({e!r})", False)
# 2. side bar content
w.show("logisim"); pump(); ex = w.side.view()
tops = ex.t.get_children("")
chk("Logisim explorer lists Project + Logisim's folders", [ex.t.item(i, "text").strip() for i in tops][:5] == ["Project", "Wiring", "Gates", "Plexers", "Arithmetic"])
chk("explorer lists the circuit 'main'", "c:main" in ex.t.get_children("proj"))
# 3. placement tool from the explorer
cv = w.pages["logisim"].views["circuit"]; d = w.doc
d.load_text(json.dumps({"inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}]})); pump()
ex.t.item("f:Gates", open=True); ex.t.selection_set("p:NAND:NAND Gate"); ex.t.event_generate("<<TreeviewSelect>>"); pump()
chk("explorer click selects the tool", cv.tool == ("part", "NAND"))
n0 = len(d.circuit.components); x, y = 300, 120
time.sleep(0.6); cv.canvas.event_generate("<Button-1>", x=x, y=y); cv.canvas.event_generate("<ButtonRelease-1>", x=x, y=y); pump()
comps = d.circuit.components; new = comps[-1]
chk("click in the circuit placed a NAND gate with floating inputs", len(comps) == n0 + 1 and new.type_name == "NAND" and not new.ins and d.valid)
chk("tool went back to Edit", cv.tool is None)
d.undo(); pump()
# toolbar: input pin tool
cv.set_tool(("in",)); pump(); chk("toolbar: Input pin tool", cv.tool == ("in",))
time.sleep(0.6); cv.canvas.event_generate("<Button-1>", x=200, y=200); cv.canvas.event_generate("<ButtonRelease-1>", x=200, y=200); pump()
chk("input pin placed", len(d.circuit.inputs) == 3)
d.undo(); pump()
cv.set_tool(("part", "AND")); pump(); cv.canvas.event_generate("<Key-Escape>"); pump(); chk("Esc cancels the tool", cv.tool is None)
# 4. Multisim component database
w.show("multisim"); pump(); cb = w.side.view(); sv = w.pages["multisim"].views["schematic"]
groups = [cb.t.item(i, "text").strip() for i in cb.t.get_children("")]
chk("component database groups", groups == ["Sources", "Basic", "Diodes", "Transistors", "Analog", "Indicators"])
n0 = len(w.adoc.netlist.parts); sv.place(AC.NPN); pump(); chk("place NPN from the bin code path", len(w.adoc.netlist.parts) == n0 + 1)
for g in sv.group_btns:
    m = ctx.menu(); from vibesimulation.ui.multisim.parts_bin import fill_group_menu; fill_group_menu(m, ctx, g, sv.place)
w.adoc.undo(); pump()
# 5. side bar toggle and activity bar
open0 = w.side.winfo_ismapped(); w.toggle_side(); pump(); chk("Ctrl+B / toggle hides the side bar", open0 and not w.side.winfo_ismapped())
w.toggle_side(); pump(); chk("toggle shows it again", w.side.winfo_ismapped())
w.activity("multisim"); pump(); chk("clicking the active activity icon hides the side bar", not w.side.winfo_ismapped()); w.activity("multisim"); pump()
w.show("settings"); pump(); chk("settings page has the category side bar", w.side.winfo_ismapped() and w.side.view().__class__.__name__ == "SettingsNav")
m = None
try: w.manage_menu(100, 100); pump(); ctx.close_popups()
except Exception as e: chk(f"gear menu ({e!r})", False)
# 6. settings: commonly used and search
sp = w.pages["settings"]; sp.pick("Commonly Used"); pump(); chk("Commonly Used shows rows", len(sp.rows.winfo_children()) >= 5)
sp.q.set("theme"); pump(); chk("search finds settings", "found" in sp.count.cget("text")); sp.q.set(""); pump()
ctx.cfg.clear(); ctx.save_cfg()
print("ALL OK" if ok else "SOME FAILED")
