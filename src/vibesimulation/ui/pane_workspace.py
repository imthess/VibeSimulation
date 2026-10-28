"""Shared frame of the Logisim and Multisim workspaces: three panes that can be swapped and hidden."""
import tkinter as tk

from .widgets import Btn


class PaneWorkspace(tk.Frame):
    """Three panes (big one on the left, two stacked on the right) that can be swapped and hidden. Subclasses say which panes."""
    KEY, NAMES, DEFAULT = "logisim", {"circuit": "Circuit", "json": "Circuit JSON", "table": "Truth table"}, ["circuit", "json", "table"]
    EDITOR = "json"                 # the pane that holds typed text (flushed before undo / save)

    def make_views(self, ctx, doc):
        raise NotImplementedError

    def editor(self): return self.views[self.EDITOR]

    def __init__(self, ctx, master, shell, doc):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        cfg = ctx.cfg
        k_order, k_hidden = ("order", "hidden") if self.KEY == "logisim" else (self.KEY + "_order", self.KEY + "_hidden")
        self.k_order, self.k_hidden = k_order, k_hidden
        self.order = [k for k in cfg.get(k_order, self.DEFAULT) if k in self.DEFAULT]
        if sorted(self.order) != sorted(self.DEFAULT): self.order = list(self.DEFAULT)
        self.hidden = {k for k in cfg.get(k_hidden, []) if k in self.DEFAULT}
        self.views = self.make_views(ctx, doc)
        for k, v in self.views.items():
            Btn(ctx, v.card.chrome, "–", lambda k=k: self.toggle(k), "ghost", padx=8, pady=0, font=ctx.f_icon).tip("Hide this pane").pack(side="right")
            b = Btn(ctx, v.card.chrome, "⇄", None, "ghost", padx=8, pady=0, font=ctx.f_icon).tip("Swap position with another pane")
            b.cmd = lambda k=k, b=b: self.swap_menu(k, b); b.pack(side="right")
        self.empty = tk.Label(self, text="All panes are hidden.\nUse  View  in the top bar to show them again.", font=ctx.f_body, justify="center")
        ctx.themed.append(lambda: (self.configure(bg=ctx.P["bg"]), self.empty.configure(bg=ctx.P["bg"], fg=ctx.P["muted"]))); self.configure(bg=ctx.P["bg"])
        self.layout()

    # ---- arranging
    def layout(self):
        vis = [k for k in self.order if k not in self.hidden]
        for v in self.views.values(): v.card.grid_forget()
        self.empty.grid_forget()
        for i in range(3):
            self.columnconfigure(i, weight=0, uniform=""); self.rowconfigure(i, weight=0, uniform="")
        g = dict(sticky="nsew", padx=0, pady=0)
        if len(vis) == 3:
            self.views[vis[0]].card.grid(row=0, column=0, rowspan=2, **dict(g, padx=(0, 1)))
            self.views[vis[1]].card.grid(row=0, column=1, **dict(g, pady=(0, 1))); self.views[vis[2]].card.grid(row=1, column=1, **g)
            self.columnconfigure(0, weight=3, uniform="c"); self.columnconfigure(1, weight=2, uniform="c")
            for r in (0, 1): self.rowconfigure(r, weight=1, uniform="r")
        elif len(vis) == 2:
            for c, k in enumerate(vis): self.views[k].card.grid(row=0, column=c, **dict(g, padx=(0, 1) if c == 0 else 0)); self.columnconfigure(c, weight=1, uniform="c")
            self.rowconfigure(0, weight=1)
        elif len(vis) == 1:
            self.views[vis[0]].card.grid(row=0, column=0, **g); self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)
        else:
            self.empty.grid(row=0, column=0, sticky="nsew"); self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)
        self.ctx.cfg[self.k_order], self.ctx.cfg[self.k_hidden] = self.order, sorted(self.hidden)
        self.ctx.save_cfg()

    def toggle(self, key):
        self.hidden.symmetric_difference_update({key}); self.layout()

    def swap_menu(self, key, btn):
        m = self.ctx.menu()
        m.add_command(label=f"Swap {self.NAMES[key]} with…", state="disabled")
        for other in self.order:
            if other != key: m.add_command(label="    " + self.NAMES[other], command=lambda o=other: self.swap(key, o))
        m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def swap(self, a, b):
        i, j = self.order.index(a), self.order.index(b); self.order[i], self.order[j] = self.order[j], self.order[i]; self.layout()

    def reset(self):
        self.order, self.hidden = list(self.DEFAULT), set(); self.layout()
