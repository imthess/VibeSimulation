"""The AI assistant button: a round button at the bottom right of every page; it opens a prompt bar that edits the circuit, its JSON or its code.

This file ties the pieces together: ``fab.py`` (the button), ``bar.py`` (text box, message, panel), ``backdrop.py`` (glass painting and the
picture behind the overlay), ``session.py`` (one AI request with automatic repair) and ``targets.py`` (what each workspace sends and accepts)."""
import tkinter as tk
from tkinter import ttk

from vibesimulation.ui.assistant.backdrop import Under
from vibesimulation.ui.assistant.bar import Bubble, Field, Panel
from vibesimulation.ui.assistant.fab import Fab
from vibesimulation.ui.assistant.session import NeedSetup, Session
from vibesimulation.ui.assistant.targets import KEYS, NAMES, target_for
from vibesimulation.ui.controls.widgets import Segmented
from vibesimulation.workspaces.ai_import.core import PROVIDERS, profile
from vibesimulation.workspaces.ai_import.ui.skin import Pill
EDGE = 18            # distance of the button from the window's right and bottom edge


class AssistantUI:
    """Round button + prompt bar. Created by the main window; ``on_page`` tells it which page is shown."""

    def __init__(self, ctx, shell):
        self.ctx, self.sh = ctx, shell; self.root = ctx.root
        self.open = self.busy = False; self.mode = "edit"; self.forced = None; self.last_ws = "logisim"; self.applied = self.open_to = None
        self.fab_bg = self.panel_bg = self.fab_sig = self.panel_sig = None; self._lay = None
        self.session = Session(shell)
        self.fab = Fab(ctx, self.root, self); self.panel = Panel(ctx, self.root, self)
        self.under = Under(ctx, {self.fab, self.panel})
        self._build(); ctx.themed.append(self.repaint)
        self.root.bind("<Configure>", self._root_cfg, add="+"); self.sync()
        self.root.after(2000, self._tick)

    # ---- the bar's contents
    def _build(self):
        ctx = self.ctx; f = self.panel.inner; f.columnconfigure(0, weight=1)
        self.res = tk.Frame(f, bd=0); self.res.columnconfigure(0, weight=1)
        self.bubble = Bubble(ctx, self.res); self.bubble.grid(row=0, column=0, sticky="ew")
        self.rbtn = tk.Frame(self.res, bd=0); self.rbtn.grid(row=0, column=1, padx=(8, 0))
        self.b_undo = Pill(ctx, self.rbtn, "Undo", self.undo, "soft", height=30, width=70); self.b_open = Pill(ctx, self.rbtn, "Open", self.open_page, "soft", height=30, width=70)
        self.cfgrow = tk.Frame(f, bd=0)
        self.field = Field(ctx, f, self.send); self.field.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.bar = tk.Frame(f, bd=0); self.bar.grid(row=3, column=0, sticky="ew"); self.bar.columnconfigure(3, weight=1)
        self.chip = Pill(ctx, self.bar, "", self.pick_target, "soft", height=32, width=170); self.chip.grid(row=0, column=0, padx=(0, 8))
        self.seg = Segmented(ctx, self.bar, [("Edit", "edit"), ("Ask", "ask")], "edit", self.set_mode); self.seg.grid(row=0, column=1, padx=(0, 8))
        self.gear = Pill(ctx, self.bar, "⚙", self.toggle_cfg, "soft", height=32, shape="circle"); self.gear.grid(row=0, column=2); self.gear.tip("AI model and key")
        self.keys = tk.Label(self.bar, text="Enter to send  ·  Shift+Enter for a new line", font=ctx.f_small, anchor="e"); self.keys.grid(row=0, column=3, sticky="e", padx=10)
        self.send_btn = Pill(ctx, self.bar, "↑", self.send_or_stop, "ink", height=38, shape="circle"); self.send_btn.grid(row=0, column=4)
        self.field.txt.bind("<Escape>", lambda e: (self.close(), "break")[1]); self.panel.bind("<Escape>", lambda e: self.close())
        v = self.sh.pages["import"].view
        self.cprov = ttk.Combobox(self.cfgrow, state="readonly", values=list(PROVIDERS), textvariable=v.prov, style="Modern.TCombobox", font=ctx.f_body, width=24)
        self.cmodel = ttk.Combobox(self.cfgrow, textvariable=v.model, values=list(v.cb_model.cget("values")), style="Modern.TCombobox", font=ctx.f_body, width=26)
        self.ckey = ttk.Entry(self.cfgrow, textvariable=v.key, show="•", style="Modern.TEntry", font=ctx.f_body, width=28)
        self.cprov.bind("<<ComboboxSelected>>", lambda e: (v.provider_changed(), self._models()))
        self.cmodel.bind("<<ComboboxSelected>>", lambda e: v.model_manual()); self.cmodel.bind("<KeyRelease>", lambda e: v.model_manual() if e.keysym not in ("Tab", "Shift_L", "Shift_R") else None)
        self.clbl = [tk.Label(self.cfgrow, text=t, font=ctx.f_small, anchor="w") for t in ("Provider", "Model", "API key (paste it; the provider is detected)")]
        for i, (w, l) in enumerate(zip((self.cprov, self.cmodel, self.ckey), self.clbl)):
            self.cfgrow.columnconfigure(i, weight=1); l.grid(row=0, column=i, sticky="w", padx=(0, 8)); w.grid(row=1, column=i, sticky="ew", padx=(0, 8), pady=(2, 0))
        self.cnote = tk.Label(self.cfgrow, text="Shared with the Import & AI page. The key stays in this session unless you tick “Remember” there.", font=ctx.f_small, anchor="w")
        self.cnote.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.paint_bar(); self.update_target()

    def _models(self):
        try: self.cmodel.configure(values=list(self.sh.pages["import"].view.cb_model.cget("values")))
        except tk.TclError: pass

    def paint_bar(self):
        P = self.ctx.P
        for w in (self.res, self.rbtn, self.cfgrow, self.bar): w.configure(bg=P["card"])
        for l in (*self.clbl, self.cnote, self.keys): l.configure(bg=P["card"], fg=P["muted"])
        self.panel.configure(bg=P["bg"])

    def repaint(self):
        self.paint_bar(); self.fab.configure_size(); self.fab._key = None; self.panel._key = None; self.panel.schedule(); self.refresh(); self.fab.draw()

    # ---- showing / hiding
    def on(self): return bool(self.ctx.cfg.get("ai_button", True))

    def shown(self):
        """The button is on (Settings) and the page is not Import & AI, where a prompt bar has no use."""
        return self.on() and getattr(self.sh, "current", None) != "import"

    def sync(self):
        if self.shown():
            self.fab.place(in_=self.root, relx=1.0, rely=1.0, x=-EDGE, y=-EDGE, anchor="se"); self.lift(); self.layout(); self.root.after(80, self.refresh)
        else:
            self.fab.place_forget(); self.panel.place_forget(); self.open = False

    def lift(self):
        tk.Misc.lift(self.fab)
        if self.open: tk.Misc.lift(self.panel)

    def toggle(self):
        if not self.shown(): return
        self.close() if self.open else self.show()

    def show(self):
        if not self.shown(): return
        self.open = True; self.update_target(); self.layout(); self.lift(); self.fab.draw(); self.refresh(); self.field.focus_set()

    def close(self):
        if not self.open: return
        self.open = False; self.panel.place_forget(); self.fab.draw(); self.sh.restore_focus()

    def layout(self):
        if not self.shown(): return
        W = self.root.winfo_width(); n = self.fab.n; M = self.panel.M; T = (n - self.fab.d) // 2; vis = max(420, min(780, W - 2 * EDGE - n - 10 - 110))
        right = EDGE + n                                                 # the bar's canvas ends where the button's tile begins: the two never overlap
        key = (vis, right, self.open)
        if self.open:
            self.panel.place(in_=self.root, relx=1.0, rely=1.0, x=-right, y=-(EDGE + T - M), anchor="se", width=vis + 2 * M); tk.Misc.lift(self.panel)
            if key != self._lay: self.panel.schedule()
        self._lay = key

    def _root_cfg(self, e):
        if e.widget is self.root: self.layout(); self.root.after(120, self.refresh); self.lift()

    def on_page(self, name):
        if name in KEYS: self.last_ws = name
        self.forced = None; self.sync(); self.update_target(); self.lift(); self.root.after(150, self.refresh); self.root.after(600, self.refresh)

    # ---- what is behind the button / bar
    def refresh(self):
        """Read the colours behind the overlay again and repaint it if they changed."""
        if not self.shown() or not self.fab.winfo_ismapped(): return
        try:
            import hashlib
            n = self.fab.n; im = self.under.render(self.fab.winfo_rootx(), self.fab.winfo_rooty(), n, n); sig = hashlib.md5(im.tobytes()).hexdigest()
            if sig != self.fab_sig: self.fab_bg, self.fab_sig = im, sig; self.fab.draw()
            if self.open and self.panel.winfo_ismapped():
                W, H = self.panel.winfo_width(), self.panel.winfo_height()
                im = self.under.render(self.panel.winfo_rootx(), self.panel.winfo_rooty(), W, H); sig = hashlib.md5(im.tobytes()).hexdigest()
                if sig != self.panel_sig or self.panel_bg is None or self.panel_bg.size != im.size: self.panel_bg, self.panel_sig = im, sig; self.panel.schedule()
        except tk.TclError: pass

    def _tick(self):
        try:
            if self.shown() and self.root.winfo_viewable(): self.refresh()
            if self.busy and self.ctx.motion: self.fab.spin = (self.fab.spin - 24) % 360; self.fab.draw()
            self.root.after(120 if self.busy else 2000, self._tick)
        except tk.TclError: pass

    # ---- the target (what the AI edits)
    def target_key(self):
        if self.forced: return self.forced
        cur = getattr(self.sh, "current", None)
        return cur if cur in KEYS else self.last_ws

    def target(self): return target_for(self.sh, self.target_key())

    def update_target(self):
        t = self.target(); self.chip.configure(text=f"{t.label}  ▾", width=self.ctx.f_body.measure(f"{t.label}  ▾") + 36)
        self.field.hint(("Ask a question about this " + t.noun.lower() + "…") if self.mode == "ask" else f"Describe the change, e.g. “{t.example}”")

    def pick_target(self):
        m = self.ctx.menu(); cur = self.target_key()
        for k in KEYS: m.add_command(label=NAMES[k] + ("   ✓" if k == cur else ""), command=lambda k=k: self.set_target(k))
        b = self.chip; m.tk_popup(b.winfo_rootx(), b.winfo_rooty() - 4 - 30 * len(KEYS))

    def set_target(self, key): self.forced = key; self.update_target()

    def set_mode(self, mode): self.mode = mode; self.seg.set(mode); self.update_target()

    # ---- the setup row
    def toggle_cfg(self, on=None):
        show = (not self.cfgrow.winfo_ismapped()) if on is None else on
        if show and profile.enabled(self.ctx.cfg):                # a separate AI is set for this button: it is changed in Settings
            self.ctx.toast("The AI button uses " + profile.describe(self.ctx.cfg) + ". Change it in Settings > AI & Import.", "info"); return
        if show: self.cfgrow.grid(row=1, column=0, sticky="ew", pady=(0, 8)); self._models()
        else: self.cfgrow.grid_remove()

    # ---- messages
    def say(self, text, kind="info", key=None, show_open=False):
        """Show a message above the prompt box. key: the workspace that was just changed (gives the Undo button); show_open: also an Open button for it."""
        self.bubble.set(text, kind); self.res.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for b in (self.b_undo, self.b_open): b.grid_remove()
        if key: self.b_undo.grid(row=0, column=0)
        if key and show_open: self.b_open.grid(row=0, column=1, padx=(6, 0))
        self.applied = key; self.open_to = key
        self.panel.schedule()

    def hide_msg(self): self.res.grid_remove(); self.panel.schedule()

    # ---- sending
    def set_busy(self, on):
        self.busy = on; self.send_btn.configure(text="■" if on else "↑"); self.fab.draw()

    def send_or_stop(self):
        if self.busy: self.session.cancel(); self.set_busy(False); self.say("Stopped.", "info"); return
        self.send()

    def send(self):
        if self.busy: return
        req = self.field.get().strip()
        if not req: self.field.focus_set(); return
        t = self.target()
        try: model = self.session.start(t, req, self.mode)
        except NeedSetup as e: self.toggle_cfg(True); self.say(str(e), "bad"); return
        self.sh.pages["import"].view.settings(); self.ctx.save_cfg()
        self.set_busy(True); self.say(f"Asking {model}…  (this can take up to a minute)", "info"); self._poll()

    def _poll(self):
        try:
            for kind, val in self.session.poll():
                if kind == "status": self.say(val, "info")
                elif kind == "error": self.set_busy(False); self.say(val, "bad")
                else: self.set_busy(False); self._done(val)
            if self.busy: self.root.after(120, self._poll)
        except tk.TclError: pass

    def _done(self, info):
        key = info["key"]
        if info["kind"] == "ask": self.say(info["text"], "none"); self.field.set(""); return
        if info["kind"] == "same": self.say(info["text"], "info"); return
        self.field.set("")
        t = {"logisim": "circuit", "multisim": "circuit"}.get(key, "code")
        msg = f"✔ Updated the {t}: {info['text']}." + (f"  (fixed automatically after {info['tries'] - 1} retr{'y' if info['tries'] == 2 else 'ies'})" if info.get("tries", 1) > 1 else "")
        self.say(msg, "ok", key=key, show_open=self.sh.current != key)
        if not self.open: self.ctx.toast(f"AI: {info['text']}", "ok")

    def undo(self):
        key = self.applied
        if key is None: return
        t = target_for(self.sh, key)
        try: t.editor().flush()
        except Exception: pass
        t.doc.undo(); self.applied = None; self.b_undo.grid_remove(); self.bubble.set("Undone.", "info"); self.panel.schedule()

    def open_page(self):
        self.sh.show(self.open_to or self.target_key())
