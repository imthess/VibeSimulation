"""The bottom panel of the VLSI page: Problems | Output | Waveform, and the Run button (like the panel under a code editor)."""
import tkinter as tk

from vibesimulation.workspaces.verilog.project import simulation
from vibesimulation.ui.controls.widgets import Btn, Segmented
from vibesimulation.workspaces.verilog.simulation.output_tab import OutputTab
from vibesimulation.workspaces.verilog.simulation.problems_tab import ProblemsTab
from vibesimulation.workspaces.verilog.simulation.waveform_tab import WaveformTab
class BottomDock(tk.Frame):
    HEIGHTS = (150, 230, 330)

    def __init__(self, ctx, master, doc, page):
        super().__init__(master, bd=0); self.ctx, self.doc, self.page = ctx, doc, page
        self.size = 1; self.open = True
        head = tk.Frame(self, bd=0); head.pack(fill="x"); self.head = head
        self.tabs = Segmented(ctx, head, [("Problems", "problems"), ("Output", "output"), ("Waveform", "wave")], "problems", self.show)
        self.tabs.pack(side="left", padx=(10, 8), pady=4)
        self.b_run = Btn(ctx, head, "▶ Run", self.run, "primary", padx=12, pady=2); self.b_run.tip("Simulate the design in time (Ctrl+Enter)"); self.b_run.pack(side="left", padx=4)
        self.b_mode = Btn(ctx, head, "random inputs", self.next_mode, "ghost", padx=8, pady=2); self.b_mode.tip("What drives the inputs when there is no testbench: random values or counting up")
        self.b_mode.pack(side="left", padx=4)
        Btn(ctx, head, "⚙ Settings", self.settings, "ghost", padx=8, pady=2).tip("Simulation settings: top module, standard, -D / -I, time limit, warnings, command lines").pack(side="left", padx=2)
        self.lbl = tk.Label(head, text="", font=ctx.f_small, anchor="w"); self.lbl.pack(side="left", padx=10)
        Btn(ctx, head, "▾", self.toggle, "ghost", padx=8, pady=0, font=ctx.f_icon).tip("Hide or show this panel").pack(side="right", padx=4)
        Btn(ctx, head, "⤢", self.grow, "ghost", padx=8, pady=0, font=ctx.f_icon).tip("Make this panel taller or shorter").pack(side="right")
        self.body = tk.Frame(self, bd=0); self.body.pack(fill="both", expand=True)
        self.tab = {"problems": ProblemsTab(ctx, self.body, doc, page), "output": OutputTab(ctx, self.body), "wave": WaveformTab(ctx, self.body)}
        self.cur = None
        ctx.themed.append(self.paint); self.paint(); self.show("problems")
        doc.subscribe(self.on_doc); self.on_doc("problems")

    mode = property(lambda s: s.doc.sim_settings.stimulus, lambda s, v: setattr(s.doc.sim_settings, "stimulus", v))
    cycles = property(lambda s: s.doc.sim_settings.cycles, lambda s, v: setattr(s.doc.sim_settings, "cycles", v))

    def paint(self):
        P = self.ctx.P
        self.configure(bg=P["border"], height=self.HEIGHTS[self.size])
        self.head.configure(bg=P["card"]); self.lbl.configure(bg=P["card"], fg=P["muted"]); self.body.configure(bg=P["field"])
        for t in self.tab.values(): t.configure(bg=P["field"])

    def show(self, key):
        if key == self.cur: return
        if self.cur: self.tab[self.cur].pack_forget()
        self.cur = key; self.tab[key].pack(fill="both", expand=True); self.tabs.set(key)
        if not self.open: self.toggle()

    def settings(self):
        from vibesimulation.workspaces.verilog.simulation.sim_dialog import SimDialog
        names = sorted(self.doc.circuits) + [n for n in __import__("re").findall(r"\bmodule\s+([A-Za-z_]\w*)", self.doc.tb_text or "")]
        SimDialog(self.ctx, self, self.doc, sv=getattr(self.page, "KEY", "") == "systemverilog", modules=list(dict.fromkeys(names)))

    def next_mode(self):
        self.mode = "count" if self.mode == "random" else "random"; self.b_mode.configure(text="counting inputs" if self.mode == "count" else "random inputs")

    def toggle(self):
        self.open = not self.open
        if self.open: self.body.pack(fill="both", expand=True)
        else: self.body.pack_forget()
        self.configure(height=self.HEIGHTS[self.size] if self.open else 36); self.page.layout()

    def grow(self):
        self.size = (self.size + 1) % len(self.HEIGHTS); self.configure(height=self.HEIGHTS[self.size])
        if not self.open: self.toggle()
        else: self.page.layout()

    def on_doc(self, kind):
        if kind != "problems": return
        self.tab["problems"].refresh(); e, w = self.tab["problems"].counts()
        self.tabs.opts[0] = (f"Problems  ✘{e}  ⚠{w}" if (e or w) else "Problems", "problems"); self.tabs.paint()

    def run(self):
        self.page.editor().flush()                                   # whatever was typed last is part of the design
        self.lbl.configure(text="running…"); self.update_idletasks()
        res, text = simulation.run(self.doc, cycles=self.cycles, mode=self.mode)
        self.doc.last_run = res
        written = bool(self.doc.tb_text.strip()) and "vs_auto_tb" not in text
        label = "your testbench" if written else f"generated testbench ({self.cycles} clock cycles, {'random' if self.mode == 'random' else 'counting'} inputs)"
        self.tab["output"].show(res, label)
        if res.error:
            self.show("output"); self.page.goto_line(getattr(res.error, "line", 0), in_tb=written)
        else:
            self.tab["wave"].doc = self.doc; self.tab["wave"].show(res); self.show("wave" if res.waves else "output")
        self.lbl.configure(text=("✘ stopped on an error" if res.error else f"finished at time {res.end_time}"))
