import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DISPLAY", ":97")
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx; w.show("import"); root.update(); v = w.pages["import"].view
for f in ("a.png", "a.jpg", "a.webp"):
    ctx.choose_file = lambda *a, **k: "/tmp/pv/" + f
    v.pick_image(); root.update(); root.after(300); root.update()
    print(f, "image" if v.lbl_prev.cget("image") else "NO IMAGE", repr(v.lbl_prev.cget("text")), v.prev_box.winfo_width(), v.prev_box.winfo_height())
os.system("import -display :97 -window root /tmp/pv/shot.png")
import vibesimulation.ui.ai_import.import_view as iv, time
iv.ask_model = lambda *a: (time.sleep(1.0), '{"inputs":["A"],"outputs":{"Y":"A"},"components":[]}')[1]
v.key.set("x"); v.model.set("m"); said = []; ctx.say = lambda *a: said.append(a)
v.convert(); root.update()
print("busy", v.busy, [b.on for b in (v.btn_img, v.btn_paste, v.btn_f1, v.btn_f2, v.btn_convert)])
ctx.choose_file = lambda *a, **k: "/tmp/pv/a.png"; v.pick_image(); v.paste_image(); v.open_circuit_file("logisim"); print("said", len(said))
t = time.time()
while v.busy and time.time() - t < 5: root.update(); time.sleep(.05)
print("after", v.busy, [b.on for b in (v.btn_img, v.btn_paste, v.btn_f1, v.btn_f2, v.btn_convert)])
