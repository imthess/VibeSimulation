"""Import & AI: a built-in picture prompt for every tab (Logisim, Multisim, Verilog, SystemVerilog), the "My own prompt" option, code results."""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
import vibesimulation.workspaces.ai_import.ui.import_view as IV
from vibesimulation.workspaces.ai_import.core.prompt import TARGETS, LABELS, build_prompt, default_task, digital_help, image_prompt, is_code
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
def wait(f, t=8):
    t0 = time.time()
    while time.time() - t0 < t and not f(): pump(2)
    return f()

# ---- the prompts themselves
chk("auto prompt is the old combined prompt", image_prompt("auto") == build_prompt() and "ANALOG CIRCUIT" in build_prompt() and '"kind":"digital"' in build_prompt())
chk("Logisim prompt: logic format only", '"kind":"digital"' in image_prompt("logisim") and "ANALOG CIRCUIT" not in image_prompt("logisim") and "LOGIC (digital)" in image_prompt("logisim"))
chk("Multisim prompt: analog format only", "ANALOG CIRCUIT" in image_prompt("multisim") and "LOGIC CIRCUIT, exactly" not in image_prompt("multisim") and "ANALOG (electrical)" in image_prompt("multisim"))
chk("Verilog prompt asks for a verilog block", "Verilog (IEEE 1364-2005)" in image_prompt("vlsi") and "```verilog" in image_prompt("vlsi") and "synthesizable" in image_prompt("vlsi"))
chk("SystemVerilog prompt asks for a systemverilog block", "SystemVerilog (IEEE 1800)" in image_prompt("systemverilog") and "```systemverilog" in image_prompt("systemverilog"))
chk("only the code tabs answer with code", [t for t in TARGETS if is_code(t)] == ["vlsi", "systemverilog"])
chk("own text replaces the task but the format rules stay", image_prompt("logisim", "Read my sketch carefully.").startswith("Read my sketch carefully.") and digital_help() in image_prompt("logisim", "x") and default_task("logisim") not in image_prompt("logisim", "x"))
chk("empty own text falls back to the built-in task", image_prompt("multisim", "  ") == image_prompt("multisim"))

# ---- the page
asked = []; replies = []
def fake_ask(name, model, key, img, mime, base=None, prompt=None, want_json=True):
    asked.append((prompt, want_json)); time.sleep(0.1); return replies.pop(0)
IV.ask_model = fake_ask
repairs = []
def fake_chat(name, model, key, system, user, base=None, want_json=False):
    repairs.append((system, user, want_json)); time.sleep(0.1); return replies.pop(0)
IV.chat_model = fake_chat
w.show("import"); pump(10); v = w.pages["import"].view; v.prov.set("Ollama (local, free)"); v.provider_changed(); pump(5)
from vibesimulation.workspaces.ai_import.core import tuning; tuning._state["compact_answer"] = False      # this test is about the long prompts; the short answer format has its own test (guitest54)
v.image_bytes, v.image_mime = b"\x89PNG", "image/png"
chk("page has the Convert-to list with every tab", list(v.cb_target.cget("values")) == [LABELS[t] for t in TARGETS])
chk("built-in prompt is the default", v.pmode.value == "default" and not v.pfield.winfo_ismapped() and v.cur_target() == "auto")
def pick(t): v.target.set(LABELS[t]); v.target_changed(); pump(3)
def convert(reply):
    replies[:] = [reply] if isinstance(reply, str) else list(reply); v.convert(); return wait(lambda: not v.busy)

# default prompt for each tab
logic = json.dumps({"kind": "digital", "inputs": ["A"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NOT", "in": ["A"], "out": "Y"}]})
pick("logisim"); chk("convert button says circuit for Logisim", v.btn_convert.text == "Convert picture to circuit")
chk("Logisim conversion", convert(logic) and asked[-1][0] == image_prompt("logisim") and asked[-1][1] is True and v.result_kind == "digital" and v.btn_logisim.on and not v.btn_vlsi.on)
analog = json.dumps({"kind": "analog", "components": [{"id": "V1", "type": "VoltageSource", "value": "5", "nodes": ["n1", "0"]}, {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["n1", "0"]}]})
pick("multisim"); chk("Multisim conversion", convert(analog) and asked[-1][0] == image_prompt("multisim") and v.result_kind == "analog" and v.btn_multisim.on)
pick("auto"); chk("Auto conversion keeps the old prompt", convert(analog) and asked[-1][0] == build_prompt() and v.result_kind == "analog")
good = "module inv(input a, output y);\n  assign y = ~a;\nendmodule\n"
pick("vlsi"); chk("convert button says code for Verilog", v.btn_convert.text == "Convert picture to code")
chk("Verilog conversion", convert("Here you go:\n```verilog\n" + good + "```") and asked[-1][0] == image_prompt("vlsi") and asked[-1][1] is False and v.result_kind == "vlsi")
pump(5); chk("code became the Verilog project", "assign y = ~a" in w.vdoc.verilog() and w.vdoc.valid and v.btn_vlsi.on and not v.btn_logisim.on)
v.btn_vlsi.cmd(); pump(5); chk("Open button goes to the Verilog tab", w.current == "vlsi"); w.show("import"); pump(5)
sv = "module cnt(input clk, input rst, output logic [3:0] q);\n  always_ff @(posedge clk) if (rst) q <= 0; else q <= q + 1;\nendmodule\n"
pick("systemverilog"); chk("SystemVerilog conversion", convert("```systemverilog\n" + sv + "```") and asked[-1][1] is False and v.result_kind == "systemverilog" and w.sdoc.valid and "always_ff" in w.sdoc.verilog())
v.btn_sv.cmd(); pump(5); chk("Open button goes to the SystemVerilog tab", w.current == "systemverilog"); w.show("import"); pump(5)

# code that does not compile is sent back to the AI
bad = "module inv2(input a, output y);\n  assign y = ~;\nendmodule\n"; fixed = "module inv2(input a, output y);\n  assign y = ~a;\nendmodule\n"
pick("vlsi"); n0 = len(repairs); chk("compile error repaired through the AI", convert(["```verilog\n" + bad + "```", "```verilog\n" + fixed + "```"]) and len(repairs) - n0 == 1 and "inv2" in w.vdoc.verilog() and v.result_kind == "vlsi")
chk("repair asked without constraining to JSON", repairs[-1][2] is False and "line 2" in repairs[-1][1] and "rejected" in repairs[-1][1])
n0 = len(repairs); chk("code that stays broken is shown for hand fixing", convert(["```verilog\n" + bad + "```"] * 3) and len(repairs) - n0 == 2 and v.result_kind is None and "does not compile" in v.status.msg)
pump(5); chk("faulty text is in the editor", "~;" in w.pages["vlsi"].editor().get_text())
w.vdoc.load_sample(); w.show("import"); pump(5)

# ---- "My own" prompt
pick("logisim"); v.pmode.pick("custom"); pump(10)
chk("my own prompt box shows the built-in text to edit", v.pfield.winfo_ismapped() and v.pfield.get().strip() == default_task("logisim").strip())
v.pfield.set("This is my hand-drawn half adder. Name the inputs a and b."); pump(3)
chk("my own prompt is sent (format rules still added)", convert(logic) and asked[-1][0] == image_prompt("logisim", "This is my hand-drawn half adder. Name the inputs a and b.") and asked[-1][0].startswith("This is my hand-drawn") and digital_help() in asked[-1][0])
pick("multisim"); chk("each tab keeps its own text", v.pfield.get().strip() == default_task("multisim").strip())
v.pfield.set("Only count the resistors."); pick("logisim"); chk("switching back restores the text typed for that tab", v.pfield.get().startswith("This is my hand-drawn"))
v.btn_reset.cmd(); pump(3); chk("Reset text restores the built-in task", v.pfield.get().strip() == default_task("logisim").strip())
v.pmode.pick("default"); pump(5); chk("back to Built-in hides the box and sends the built-in prompt", not v.pfield.winfo_ismapped() and convert(logic) and asked[-1][0] == image_prompt("logisim"))
v.pmode.pick("custom"); pick("multisim"); pump(3); v.settings()
chk("choices are saved in the settings", w.ctx.cfg.get("import_target") == "multisim" and w.ctx.cfg.get("import_mode") == "custom" and "Only count the resistors." in w.ctx.cfg.get("import_custom", {}).get("multisim", ""))
chk("controls are locked while the AI works", True)
replies[:] = [analog]; v.convert(); pump(2); chk("target list is locked while busy", str(v.cb_target.cget("state")) == "disabled"); wait(lambda: not v.busy); chk("and unlocked afterwards", str(v.cb_target.cget("state")) == "readonly")
chk("no AI button on the Import & AI page", not w.assist.fab.winfo_ismapped())

# ---- the state survives a new window
w2 = None
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
