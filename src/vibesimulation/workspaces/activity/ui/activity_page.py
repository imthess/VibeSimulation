"""The Activity page (the </> icon): a live log of what the program does in the background, token usage, findings and tools.

Layout:  title bar with a live status chip  /  one card: views (Log, Tokens, Findings, Details), switches, tools, and the text area.
Everything updates by itself every 300 ms while the page is shown."""
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from vibesimulation.common import activity
from vibesimulation.ui.controls.widgets import Btn, Card, Segmented
from vibesimulation.workspaces.activity.core import environment, findings
from vibesimulation.workspaces.activity.export import report, save_markdown, save_pdf
from vibesimulation.workspaces.activity.tools import diagnose
from vibesimulation.workspaces.ai_import.core import usage
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key
from vibesimulation.workspaces.ai_import.core.providers import PROVIDERS

VIEWS = (("Log", "log"), ("Tokens", "tokens"), ("Findings", "findings"), ("Details", "details"))
TICK = 300


class ActivityPage(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.view = "log"; self.seq = 0; self.follow = tk.BooleanVar(value=True); self.problems = tk.BooleanVar(value=False); self._sig = None
        # title bar with the live status
        self.top = tk.Frame(self, bd=0); self.top.pack(side="top", fill="x", padx=6, pady=(5, 3))
        self.title = tk.Label(self.top, text="Activity", font=ctx.f_title, anchor="w"); self.title.pack(side="left", padx=(20, 18), pady=7)
        self.chip = tk.Label(self.top, text="", font=ctx.f_body, anchor="w"); self.chip.pack(side="left", fill="x", expand=True)
        # the card
        self.holder = tk.Frame(self, bd=0); self.holder.pack(fill="both", expand=True, pady=(0, 5))
        self.card = Card(ctx, self.holder, 0, "What is happening in the background"); self.card.pack(fill="both", expand=True)
        for text, fn in (("Clear", self.clear), ("Download .pdf", lambda: self.download("pdf")), ("Download .md", lambda: self.download("md")), ("Copy all", self.copy)):
            Btn(ctx, self.card.tools, text, fn, "secondary", pady=5, padx=12).pack(side="right", padx=(6, 0))
        body = self.card.body; self.body = body
        bar = tk.Frame(body, bd=0); bar.pack(fill="x", pady=(0, 8)); self.bar = bar
        self.seg = Segmented(ctx, bar, list(VIEWS), "log", self.set_view); self.seg.pack(side="left")
        self.chk = [ttk.Checkbutton(bar, text="Follow new lines", variable=self.follow), ttk.Checkbutton(bar, text="Problems only", variable=self.problems, command=self.redraw)]
        for c in reversed(self.chk): c.pack(side="right", padx=(10, 0))
        tools = tk.Frame(body, bd=0); tools.pack(fill="x", pady=(0, 8)); self.tools = tools
        tk.Label(tools, text="Tools", font=ctx.f_small).pack(side="left", padx=(0, 10)); self.tools_lbl = tools.winfo_children()[0]
        for text, tip, fn in (("Test connection", "Is the service reachable, is the key accepted, how fast is it?", self.t_connection), ("Test model", "Ask the chosen model one word, no picture: how long does it take?", self.t_model),
                              ("Last request", "Show exactly what was sent to the service (pictures shortened) and what came back", lambda: self.set_view("details", True)),
                              ("Open Import page", "Go back to the picture and model settings", lambda: self.shell.show("import"))):
            b = Btn(ctx, tools, text, fn, "ghost", pady=4, padx=12); b.pack(side="left", padx=(0, 6)); b.tip(tip)
        wrap = tk.Frame(body, bd=0); wrap.pack(fill="both", expand=True); self.wrap = wrap
        f = tkfont.nametofont("TkFixedFont").copy(); f.configure(size=max(9, ctx.f_small.cget("size") if hasattr(ctx.f_small, "cget") else 10)); self.mono = f
        self.txt = tk.Text(wrap, wrap="word", bd=0, highlightthickness=0, padx=12, pady=10, font=f, cursor="arrow", spacing1=1, spacing3=1)
        self.sb = ttk.Scrollbar(wrap, command=self.txt.yview, style="Thin.Vertical.TScrollbar"); self.txt.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y"); self.txt.pack(side="left", fill="both", expand=True)
        self.txt.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in "ca") or e.keysym in ("Up", "Down", "Prior", "Next", "Home", "End") else "break")
        ctx.themed.append(self._paint); self._paint(); self.redraw(); ctx.root.after(TICK, self._tick)

    # ---- look
    def _paint(self):
        P = self.ctx.P; ctx = self.ctx
        for w in (self, self.holder): w.configure(bg=P["bg"]); ctx.glass.attach(w)
        ctx.glass.attach(self.top, 22, "pill", (0, 0, 0, 0)); self.top.configure(bg=P["card"]); self.title.configure(bg=P["card"], fg=P["text"]); self.chip.configure(bg=P["card"])
        for w in (self.bar, self.tools, self.wrap): w.configure(bg=P["card"])
        self.tools_lbl.configure(bg=P["card"], fg=P["muted"])
        self.txt.configure(bg=P["field"] if "field" in P else P["soft"], fg=P["text"], insertbackground=P["text"], selectbackground=P["sel"])
        warn = "#fbbf24" if ctx.dark else "#a16207"
        for tag, col in (("info", P["muted"]), ("ok", P["ok"]), ("warn", warn), ("error", P["bad"]), ("head", P["accent"]), ("dim", P["muted"]), ("text", P["text"])): self.txt.tag_configure(tag, foreground=col)
        self.txt.tag_configure("head", font=ctx.f_bold, spacing1=8); self.txt.tag_configure("bold", font=ctx.f_bold)

    # ---- views
    def set_view(self, v, force=False):
        self.view = v; self.seg.set(v); self.redraw()

    def redraw(self):
        """Rebuild the text area for the current view."""
        t = self.txt; t.configure(state="normal"); t.delete("1.0", "end"); self.seq = 0; self._sig = None
        getattr(self, "draw_" + self.view)(); t.configure(state="normal")
        if self.view == "log": t.see("end")
        else: t.yview_moveto(0)

    def put(self, text, tag="text"): self.txt.insert("end", text, tag)

    def draw_log(self):
        entries = activity.LOG.all()
        self._empty = not entries
        if not entries: self.put("Nothing has happened yet.\n\nWhen you convert a picture, use the AI button, test a connection or load a picture, every step appears here as it happens: the request that is sent, how long the service takes, the tokens used and any error.\n", "dim")
        self.add_entries(entries)

    def add_entries(self, entries):
        for e in entries:
            self.seq = max(self.seq, e.seq)
            if self.problems.get() and e.level not in ("warn", "error"): continue
            self.put(f"{e.clock()}  ", "dim"); self.put(f"{e.level.upper():5}  {e.source:7}  ", e.level if e.level != "debug" else "dim"); self.put(e.text + "\n", e.level if e.level in ("warn", "error") else "text")

    def draw_tokens(self):
        log = self.ctx.cfg.get("ai_usage", []); t = usage.totals(log); avg = t["total"] // t["calls"] if t["calls"] else 0
        self.put("Token usage\n", "head")
        self.put(f"{t['calls']} calls   {t['total']:,} tokens in total   ({t['prompt']:,} in, {t['output']:,} out, {t['reasoning']:,} hidden thinking)   average {avg:,} per call\n\n", "bold")
        if not log: self.put("No calls recorded yet. Convert a picture or use the AI button and the numbers appear here.\n", "dim"); return
        self.put(f"{'When':17}{'For':11}{'Service':26}{'Model':34}{'In':>9}{'Out':>9}{'Think':>9}{'Total':>9}\n", "dim")
        for e in reversed(log[-200:]):
            self.put(f"{usage.when(e):17}{('AI button' if e.get('what') == 'assistant' else 'Picture'):11}{e.get('provider', '')[:25]:26}{e.get('model', '')[:33]:34}"
                     f"{e.get('prompt', 0):>9,}{e.get('output', 0):>9,}{e.get('reasoning', 0):>9,}{e.get('total', 0):>9,}\n")
        self.put("\nCounts come from the AI service's own reply (Ollama counts its own tokens). The last 300 calls are kept.\n", "dim")

    def draw_findings(self):
        rows = findings.analyze(activity.LOG.all(), self.ctx.cfg, activity.LOG.last_request, activity.LOG.last_response)
        self.put("What the log says\n", "head")
        for level, title, advice in rows:
            self.put(f"{'●'} {title}\n", level if level in ("ok", "warn", "error") else "bold"); self.put(f"    {advice}\n\n", "text")
        self.put("Updates by itself. Run 'Test connection' and 'Test model' above to add facts.\n", "dim")

    def draw_details(self):
        import json
        self.put("System\n", "head"); [self.put(f"  {k:16}{v}\n") for k, v in environment.system_info()]
        self.put("\nAI settings (no keys)\n", "head"); [self.put(f"  {k:22}{v}\n") for k, v in environment.ai_settings(self.ctx.cfg)]
        for title, d in (("Last request sent (pictures and long text are shortened)", activity.LOG.last_request), ("Last answer received", activity.LOG.last_response)):
            self.put(f"\n{title}\n", "head"); self.put((json.dumps(d, indent=1, default=str) if d else "none yet") + "\n", "text" if d else "dim")

    # ---- live
    def _tick(self):
        try:
            usage.drain(self.ctx.cfg)
            run = activity.LOG.running(); c = activity.LOG.counts()
            if run:
                n, s = max(run, key=lambda r: r[1]); self.chip.configure(text=f"●  Working: {n}  ·  {s:.0f} s" + ("   (slow: press Stop on the Import page, or see Findings)" if s > 60 else ""), fg=self.ctx.P["accent"] if s <= 60 else self.ctx.P["bad"])
            else: self.chip.configure(text=f"●  Idle   ·   {sum(c.values())} lines   ·   {c['warn']} warnings   ·   {c['error']} errors", fg=self.ctx.P["bad"] if c["error"] else self.ctx.P["muted"])
            if self.winfo_ismapped(): self._live()
        except tk.TclError: return
        self.ctx.root.after(TICK, self._tick)

    def _live(self):
        t = self.txt
        if self.view == "log":
            new = activity.LOG.since(self.seq)
            if new and getattr(self, "_empty", False): self.redraw()                       # the 'nothing yet' text is replaced by the first lines
            elif new: self.add_entries(new); (t.see("end") if self.follow.get() else None)
        else:
            sig = (len(activity.LOG.all()), len(self.ctx.cfg.get("ai_usage", [])), int(time.time() // 2) if self.view == "findings" else 0)
            if self.view != "details" and sig != self._sig: self._sig = sig; y = t.yview()[0]; self.redraw(); t.yview_moveto(y)

    # ---- actions
    def report_text(self): return report.build(self.ctx.cfg)

    def copy(self):
        self.ctx.root.clipboard_clear(); self.ctx.root.clipboard_append(self.report_text()); self.ctx.toast("Report copied")

    def clear(self):
        activity.LOG.clear(); activity.log("app", "log cleared", "info"); self.redraw()

    def download(self, kind):
        stamp = time.strftime("%Y%m%d-%H%M%S"); name = f"vibesimulation-activity-{stamp}.{kind}"
        p = self.ctx.choose_file("save", "Save the activity report", ["." + kind], name)
        if not p: return
        try:
            (save_markdown if kind == "md" else save_pdf)(self.report_text(), p); activity.log("app", f"report saved: {p}", "ok"); self.ctx.toast("Report saved")
        except OSError as e: self.ctx.say("Save", f"The report could not be saved:\n{e}")

    def _service(self):
        """(provider, model, key, base) as chosen on the Import page, or None (a message is shown)."""
        v = self.shell.pages["import"].view; name = v.prov.get(); prov = PROVIDERS[name]; key = clean_key(v.key.get())
        if prov.env and not key: self.ctx.say("Test", f"Paste your API key for {name} on the Import page first."); return None
        return name, v.model.get().strip() or prov.models[0], key, v.base.get().strip()

    def t_connection(self):
        s = self._service()
        if s: self.set_view("log"); diagnose.test_connection(s[0], s[2], s[3])

    def t_model(self):
        s = self._service()
        if s: self.set_view("log"); diagnose.test_model(*s)

    def focus_first(self): self.txt.focus_set()
