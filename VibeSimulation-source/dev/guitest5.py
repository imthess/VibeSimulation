import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root)
w.show("multisim"); wk=w.pages["multisim"]; wk.hidden={"json","results"}; wk.layout()
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
snap("a1")
tests = {
 "a2": '{"components":[{"id":"V1","type":"V","value":9,"nodes":["n1","0"]},{"id":"R1","type":"R","value":"1k","nodes":["n1","n2"]},{"id":"R2","type":"R","value":"2.2k","nodes":["n2","0"]},{"id":"R3","type":"R","value":"1k","nodes":["n1","n3"]},{"id":"D1","type":"D","nodes":["n3","0"]},{"id":"R4","type":"R","value":"470","nodes":["n2","n3"]},{"id":"C1","type":"C","value":"1u","nodes":["n3","0"]},{"id":"I1","type":"I","value":"1m","nodes":["0","n2"]}]}',
 "a3": '{"components":[{"id":"V1","type":"V","value":12,"nodes":["a","0"]},{"id":"R1","type":"R","value":"1k","nodes":["a","b"]},{"id":"R2","type":"R","value":"1k","nodes":["a","c"]},{"id":"R3","type":"R","value":"1k","nodes":["b","d"]},{"id":"R4","type":"R","value":"1k","nodes":["c","d"]},{"id":"R5","type":"R","value":"2k","nodes":["d","0"]},{"id":"R6","type":"R","value":"3k","nodes":["b","0"]},{"id":"L1","type":"L","value":"1m","nodes":["c","e"]},{"id":"R7","type":"R","value":"1k","nodes":["e","0"]}]}',
}
for k,t in tests.items():
    w.adoc.set_text(t); print(k, w.adoc.valid, w.adoc.errors, w.adoc.layout_error[:50]); snap(k)
print("DONE")
