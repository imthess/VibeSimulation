"""Setting: background."""
import colorsys
import tkinter as tk

from vibesimulation.ui.look.glass import Glass
from vibesimulation.ui.look.shapes import rrect
from vibesimulation.ui.controls.widgets import Btn, Slider
from vibesimulation.workspaces.settings.item import D
def _swatch_colour(name, dark):
    h = Glass.PRESETS.get(name)
    if h is None: return "#8fb4ff" if not dark else "#5a7fd6"                  # Aurora: a blue with a hint of the rest
    s, v = (.10, .72) if h == -1 else ((.40, 1.0) if not dark else (.60, .72))
    r, g, b = colorsys.hsv_to_rgb((215 if h == -1 else h) / 360, s, v); return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def item(page):
    ctx = page.ctx

    def make(parent):
        f = tk.Frame(parent, bd=0); names = list(Glass.PRESETS) + ["Custom"]
        cv = tk.Canvas(f, bd=0, highlightthickness=0, height=40, width=len(names) * 36 + 6, cursor="hand2"); cv.pack(side="top", anchor="e")
        row = tk.Frame(f, bd=0); row.pack(side="top", anchor="e", pady=(6, 0))
        def current(): return ctx.cfg.get("bg_style", "Aurora")
        def draw():
            try:
                cv.delete("all"); P = ctx.P; cv.configure(bg=parent.cget("bg")); f.configure(bg=parent.cget("bg")); row.configure(bg=parent.cget("bg")); cur = current()
                for i, n in enumerate(names):
                    x = 4 + i * 36
                    col = ctx.cfg.get("bg_color", "#7aa2ff") if n == "Custom" else _swatch_colour(n, ctx.dark)
                    rrect(cv, x, 6, x + 28, 34, 999, fill=col, outline=P["border"])
                    if n == "Custom" and cur != "Custom": cv.create_text(x + 14, 20, text="+", font=ctx.f_bold, fill=P["muted"])
                    if n == cur: rrect(cv, x - 3, 3, x + 31, 37, 999, outline=P["text"], width=2)
            except tk.TclError: pass
        def choose(i):
            n = names[i]
            if n == "Custom":
                from tkinter import colorchooser
                c = colorchooser.askcolor(color=ctx.cfg.get("bg_color", "#7aa2ff"), title="Background colour", parent=ctx.root)
                if not c or not c[1]: return
                ctx.cfg["bg_color"] = c[1]
            page.set("bg_style", n, "look"); draw()
        cv.bind("<Button-1>", lambda e: choose(max(0, min(len(names) - 1, int((e.x - 2) // 36)))))
        def picture():
            p = ctx.choose_file("open", "Choose a background picture", [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
            if p: ctx.cfg["bg_image"] = p; page.set("bg_style", "Picture", "look"); draw()
        Btn(ctx, row, "Picture…", picture, "secondary", pady=4, padx=12).tip("Use your own photo, blurred behind the panels").pack(side="left", padx=(0, 6))
        Btn(ctx, row, "Reset", lambda: ([ctx.cfg.pop(k, None) for k in ("bg_style", "bg_color", "bg_image", "bg_vivid")], page.shell.set_pref("bg_style", "Aurora"), draw()), "ghost", pady=4, padx=12).pack(side="left", padx=(0, 10))
        tk.Label(row, text="Intensity", font=ctx.f_small, bg=parent.cget("bg"), fg=ctx.P["muted"]).pack(side="left", padx=(0, 6))
        job = {}
        def moved(val):
            ctx.cfg["bg_vivid"] = int(val)
            if job.get("j"): f.after_cancel(job["j"])
            job["j"] = f.after(140, lambda: (ctx.save_cfg(), ctx.glass.repaint()))
        sc = Slider(ctx, row, int(ctx.cfg.get("bg_vivid", 60)), moved, width=120); sc.pack(side="left")
        page.setters["bg_style"] = lambda: (setattr(sc, "value", int(ctx.cfg.get("bg_vivid", 60))), sc.draw(), draw()); f.bind("<Map>", lambda e: draw()); draw()
        ctx.themed.append(draw)
        return f
    return D("Appearance", "Background", "Colour behind the glass panels: a preset, any colour you pick, or your own picture. Intensity sets how vivid the glow is.", make)
