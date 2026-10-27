import sys, os, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx
saved = copy.deepcopy(ctx.cfg)
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
def ok(c, m): print(("PASS " if c else "FAIL ")+m)
def key(widget, seq):
    widget.focus_force(); root.update(); widget.event_generate(seq); root.update(); time.sleep(0.05); root.update()
root.focus_force(); root.update()
# palette via keyboard
key(root, "<Control-k>"); ok(w.palette is not None, "ctrl+k opens palette")
w.palette.q.set("teal"); root.update(); ok(len(w.palette.items)==1 and "Teal" in w.palette.items[0].title, "palette filter")
snap("k1")
key(w.palette.e, "<Return>"); time.sleep(0.2); root.update(); ok(ctx.cfg.get("accent")=="Teal" and w.palette is None, "palette runs command")
# navigation shortcuts
for seq, pg in (("<Control-Key-2>","logisim"),("<Control-Key-4>","multisim"),("<Control-Key-3>","import"),("<Control-comma>","settings"),("<Control-Key-1>","home")):
    key(root, seq); time.sleep(0.05); root.update(); ok(w.current==pg, f"{seq}->{pg}")
# text widget must not eat shortcuts
w.show("logisim"); jt = w.pages["logisim"].views["json"].txt; before = jt.get("1.0","end")
key(jt, "<Control-Key-4>"); ok(w.current=="multisim", "ctrl+4 from text"); w.show("logisim")
key(jt, "<Control-k>"); ok(w.palette is not None, "ctrl+k inside text (not kill-line)"); key(w.palette.e, "<Escape>"); ok(w.palette is None, "esc closes palette")
ok(jt.get("1.0","end")==before, "json text untouched")
# text size
key(root, "<Control-equal>"); ok(ctx.cfg.get("text_scale")==115, f"zoom in {ctx.cfg.get('text_scale')}")
key(root, "<Control-minus>"); key(root, "<Control-minus>"); ok(ctx.cfg.get("text_scale")==85, "zoom out"); key(root, "<Control-0>"); ok(ctx.cfg.get("text_scale")==100, "zoom reset")
# settings keyboard
w.show("settings"); sp = w.pages["settings"]; root.update()
seg = [x for x in sp.rows.winfo_children()]
from vibesimulation.ui.widgets import Segmented, Switch, Btn
def find(wd, cls, out):
    for c in wd.winfo_children():
        if isinstance(c, cls): out.append(c)
        find(c, cls, out)
    return out
segs = find(sp.rows, Segmented, []); sws = find(sp.rows, Switch, [])
t = segs[0]; t.focus_force(); root.update(); t.event_generate("<Left>"); root.update(); ok(ctx.cfg.get("mode") in ("light","dark"), f"segmented arrows -> {ctx.cfg.get('mode')}")
sw = find(sp.rows, Switch, [])[0]; v0 = sw.var.get(); sw.focus_force(); root.update(); sw.event_generate("<space>"); root.update(); ok(sw.var.get()!=v0, "switch space")
sw.event_generate("<space>"); root.update()
# search
sp.q.set("contrast"); root.update(); ok(len(find(sp.rows, Switch, []))==1, "settings search"); snap("k2"); sp.q.set("")
# appearances
def look(name, **cfg):
    ctx.cfg.update(cfg); ctx.refresh(); w.after_look(); snap(name)
look("k3", mode="dark", accent="Teal", corners="Pill", density="Compact", text_scale=115); w.show("home"); snap("k4"); w.show("logisim"); snap("k5"); w.show("multisim"); snap("k6")
w.open_palette(); snap("k7"); w.palette.close()
ctx.toast("Saved  ·  /tmp/example.json", "ok"); snap("k8")
look("k9", mode="light", accent="Rose", corners="Sharp", density="Spacious", text_scale=100); w.show("settings"); snap("k10")
ctx.cfg.clear(); ctx.cfg.update(saved); ctx.save_cfg()
print("DONE")
