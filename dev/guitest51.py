"""AI assistant button: round glass button on every page except Import & AI, prompt bar, edits for Logisim / Multisim / Verilog, auto-repair, Ask mode, Undo, setting."""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
import vibesimulation.ui.assistant.session as S
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear(); a = w.assist
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
def wait(f, t=6):
    t0 = time.time()
    while time.time() - t0 < t and not f(): pump(2)
    return f()
calls = []; replies = []
def fake(name, model, key, system, user, base=None, want_json=False):
    calls.append((system, user, want_json)); time.sleep(0.15); return replies.pop(0)
S.chat_model = fake
v = w.pages["import"].view; v.prov.set("Ollama (local, free)"); v.provider_changed(); pump(5)

for pg in ("home", "logisim", "multisim", "vlsi", "systemverilog", "import", "settings"):
    w.show(pg); pump(8)
    if pg == "import": chk("button is hidden on Import & AI", not a.fab.winfo_ismapped() and not a.panel.winfo_ismapped()); a.toggle(); pump(3); chk("Ctrl+J / toggle does nothing on Import & AI", not a.open); continue
    chk(f"button visible on {pg}", a.fab.winfo_ismapped() and a.fab.winfo_rootx() + a.fab.winfo_width() >= root.winfo_rootx() + root.winfo_width() - 30 and a.fab.winfo_rooty() + a.fab.winfo_height() >= root.winfo_rooty() + root.winfo_height() - 30)
w.show("logisim"); pump(10)
chk("circle button is on top of the page", root.winfo_children().index(a.fab) > root.winfo_children().index(w.mid))
a.fab.event_generate("<ButtonRelease-1>", x=5, y=5); pump(15); chk("click opens the bar", a.open and a.panel.winfo_ismapped())
chk("bar is horizontal (wider than tall)", a.panel.winfo_width() > 3 * a.panel.winfo_height())
chk("bar sits left of the button, same bottom", a.panel.winfo_rootx() + a.panel.winfo_width() <= a.fab.winfo_rootx() + 20 and abs((a.panel.winfo_rooty() + a.panel.winfo_height()) - (a.fab.winfo_rooty() + a.fab.winfo_height())) < 30)
chk("colours behind the bar were read", a.panel_bg is not None and a.fab_bg is not None)
a.field.txt.event_generate("<Escape>"); pump(8); chk("Escape closes", not a.open)
w.root.event_generate("<Control-Key-j>"); pump(10); chk("Ctrl+J opens", a.open); w.root.event_generate("<Control-Key-j>"); pump(10); chk("Ctrl+J closes", not a.open)

# ---- Logisim edit
a.show(); pump(5); chk("target on Logisim page", a.target_key() == "logisim")
new = {"kind": "digital", "inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NAND", "in": ["A", "B", "C"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["C"], "out": "n2"}, {"id": "g3", "type": "NOR", "in": ["n1", "n2"], "out": "n3"}, {"id": "g4", "type": "NOT", "in": ["n3"], "out": "Y"}]}
before = w.doc.text; replies[:] = ["Sure! ```json\n" + json.dumps(new) + "\n```"]; a.field.set("add a NOT gate before the output"); a.send(); chk("busy while asking", a.busy)
chk("edit applied", wait(lambda: not a.busy and '"g4"' in w.doc.text)); pump(5)
chk("request carried the circuit and the request", "add a NOT gate" in calls[-1][1] and '"g1"' in calls[-1][1] and calls[-1][2] is True)
chk("status says what changed", "g4" in a.bubble.msg and a.b_undo.winfo_ismapped())
chk("circuit is valid and has 4 parts", w.doc.valid and len(w.doc.circuit.components) == 4)
a.undo(); pump(8); chk("Undo restores the circuit", w.doc.text == before)

# ---- repair loop (first answer invalid)
bad = dict(new); bad = {"inputs": ["A"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "FROB", "in": ["A"], "out": "Y"}]}
n0 = len(calls); replies[:] = [json.dumps(bad), json.dumps(new)]; a.field.set("add a NOT gate"); a.send()
chk("auto-repair then applied", wait(lambda: not a.busy and '"g4"' in w.doc.text) and len(calls) - n0 == 2)
chk("repair call lists the problem", "rejected" in calls[-1][1] and "FROB" in calls[-1][1]); chk("message mentions retry", "retr" in a.bubble.msg)
w.doc.undo(); pump(3)
n0 = len(calls); replies[:] = [json.dumps(bad)] * 3; a.field.set("x"); a.send()
chk("gives up after 3 tries with an error", wait(lambda: not a.busy) and len(calls) - n0 == 3 and a.bubble.kind == "bad" and '"g4"' not in w.doc.text)

# ---- Ask mode leaves the circuit alone
a.set_mode("ask"); replies[:] = ["It is a NOR of a NAND and an inverted C."]; t0 = w.doc.text; a.field.set("what does it do?"); a.send()
chk("ask shows an answer", wait(lambda: not a.busy) and "NOR" in a.bubble.msg and w.doc.text == t0 and calls[-1][2] is False)
a.set_mode("edit")

# ---- same answer -> "unchanged"
replies[:] = [w.doc.text]; a.field.set("do nothing"); a.send(); chk("unchanged answer is reported", wait(lambda: not a.busy) and "unchanged" in a.bubble.msg)

# ---- Multisim
w.show("multisim"); pump(8); a.show(); pump(5); chk("target follows the page (Multisim)", a.target_key() == "multisim" and a.chip.text.startswith("Multisim"))
t = json.loads(w.adoc.text); t["components"][1]["value"] = "4.7k"; t["kind"] = "analog"
replies[:] = [json.dumps(t)]; a.field.set("change R1 to 4.7k"); a.send()
chk("Multisim edit applied", wait(lambda: not a.busy and "4.7k" in w.adoc.text) and w.adoc.valid and "R1" in a.bubble.msg)
chk("analog rules sent", "ANALOG" in calls[-1][0] or "analog" in calls[-1][0])
a.undo(); pump(5); chk("Multisim undo", "4.7k" not in w.adoc.text)
replies[:] = [json.dumps(new)] * 3; a.field.set("x"); a.send(); chk("logic answer is refused in Multisim", wait(lambda: not a.busy) and a.bubble.kind == "bad" and "Logisim" in a.bubble.msg)

# ---- Verilog (with a compile error repaired)
w.show("vlsi"); pump(10); a.show(); pump(5); chk("target Verilog", a.target_key() == "vlsi")
good = "module inv(input a, output y);\n  assign y = ~a;\nendmodule\n"; badv = "module inv(input a, output y);\n  assign y = ~;\nendmodule\n"
n0 = len(calls); replies[:] = ["```verilog\n" + badv + "```", "```verilog\n" + good + "```"]; a.field.set("make it an inverter"); a.send()
chk("Verilog repaired and compiled", wait(lambda: not a.busy and "~a" in w.vdoc.verilog()) and len(calls) - n0 == 2); chk("compile error sent back", "line" in calls[-1][1] and "expected" in calls[-1][1])
pump(10); chk("editor shows the new code", "assign y = ~a" in w.pages["vlsi"].editor().get_text() and w.vdoc.valid)
a.undo(); pump(8)
# testbench area
ed = w.pages["vlsi"].editor(); ed.switch("tb"); pump(5); a.update_target(); chk("testbench area detected", a.target().label.endswith("testbench"))
tb = "module tb;\n  reg a; wire y;\n  initial begin a = 0; #1 $display(\"%b\", a); $finish; end\nendmodule\n"
replies[:] = ["```verilog\n" + tb + "```"]; a.field.set("write a testbench"); a.send(); chk("testbench replaced", wait(lambda: not a.busy and "$finish" in w.vdoc.tb_text)); ed.switch("design"); pump(5)

# ---- SystemVerilog target
w.show("systemverilog"); pump(8); chk("target SystemVerilog", a.target_key() == "systemverilog" and "SystemVerilog" in a.target().system())

# ---- other pages: target = last workspace, can be changed
w.show("home"); pump(5); chk("home targets last workspace", a.target_key() == "systemverilog")
a.set_target("logisim"); chk("chip target can be changed", a.target_key() == "logisim" and a.chip.text.startswith("Logisim")); w.show("settings"); pump(3); chk("choice resets on page change", a.target_key() == "systemverilog")
a.set_target("logisim"); replies[:] = [json.dumps(new)]; a.field.set("add a NOT"); a.send(); wait(lambda: not a.busy); pump(8); chk("edit from another page works", wait(lambda: not a.busy and '"g4"' in w.doc.text) and a.b_open.winfo_ismapped())
a.open_page(); pump(5); chk("Open button goes to the workspace", w.current == "logisim")

# ---- no key
v.prov.set("Gemini (free tier)"); v.provider_changed(); v.key.set(""); pump(3); a.field.set("hello"); a.send(); pump(8)
chk("missing key asks for setup", not a.busy and a.cfgrow.winfo_ismapped() and "key" in a.bubble.msg.lower())
chk("setup row shares the import page's key", a.ckey.cget("textvariable") == str(v.key))

# ---- looks
for mode in ("dark", "light"):
    w.ctx.cfg["mode"] = mode; w.ctx.refresh(); w.after_look(); pump(15); chk(f"repaints in {mode}", a.fab.winfo_ismapped() and a.panel.winfo_ismapped())
w.ctx.cfg["glass"] = False; w.ctx.refresh(); w.after_look(); pump(10); chk("works with glass off", a.fab.winfo_ismapped()); w.ctx.cfg["glass"] = True; w.ctx.refresh(); w.after_look()
from vibesimulation.workspaces.settings.registry import all_items
chk("Settings has the switch", any(d["label"] == "AI assistant button" for d in all_items(w.pages["settings"])))
w.ctx.cfg["ai_button"] = False; w.after_look(); pump(8); chk("setting hides button and bar", not a.fab.winfo_ismapped() and not a.panel.winfo_ismapped())
w.ctx.cfg["ai_button"] = True; w.after_look(); pump(8); chk("setting shows button again", a.fab.winfo_ismapped())
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
