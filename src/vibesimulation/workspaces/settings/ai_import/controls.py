"""Small controls shared by the AI & Import settings."""
import tkinter as tk

from vibesimulation.ui.controls.widgets import Slider


def slider(page, key, default, caption, after=None):
    """A 0-100 slider with a number, saved in ``cfg[key]`` (a short moment after the last move)."""
    def make(parent):
        ctx = page.ctx; f = tk.Frame(parent, bd=0, bg=parent.cget("bg")); job = {}
        n = tk.Label(f, text=str(int(ctx.cfg.get(key, default))), width=4, font=ctx.f_small, bg=parent.cget("bg"), fg=ctx.P["muted"])
        def moved(v):
            n.config(text=str(int(v))); ctx.cfg[key] = int(v)
            if job.get("j"): f.after_cancel(job["j"])
            job["j"] = f.after(200, lambda: (ctx.save_cfg(), after() if after else None))
        sc = Slider(ctx, f, int(ctx.cfg.get(key, default)), moved, width=150); sc.pack(side="left"); n.pack(side="left", padx=(6, 0))
        def sync(): v = int(ctx.cfg.get(key, default)); sc.value = v; sc.draw(); n.config(text=str(v))
        page.setters[key] = sync
        return f
    return make
