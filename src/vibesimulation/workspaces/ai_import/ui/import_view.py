"""Box 1: pick an image and let an AI model turn it into circuit JSON."""
import base64
import io
import json
import math
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from vibesimulation.workspaces.ai_import.core import PROVIDERS, ask_model, chat_model, explain_error, extract_json, ollama_models, ollama_pull
import vibesimulation.workspaces.ai_import.core.secrets as secrets
from vibesimulation.workspaces.ai_import.core.prompt import LABELS, PAGES, TARGETS, code_system, default_task, image_prompt, is_code, repair_prompt
from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import compact, providers, scan, tuning, usage
from vibesimulation.workspaces.ai_import.core.autodetect import call_with_fallback, discover
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key, detect_provider
from vibesimulation.workspaces.multisim.core.netlist import dumps as adumps, parse as aparse
from vibesimulation.workspaces.logisim.core.serializer import dumps, parse
from vibesimulation.workspaces.ai_import.imports import classify, load_file
from vibesimulation.ui.assistant.targets import extract_code
from vibesimulation.ui.assistant.bar import Field
from vibesimulation.ui.controls.widgets import Btn, Notice, Segmented
from vibesimulation.workspaces.ai_import.ui.skin import Pill, SoftCard, tokens
from vibesimulation.workspaces.ai_import.ui.viewer import PictureViewer
from vibesimulation.ui.views.base import View
try:
    from PIL import Image
except Exception:                      # Pillow is optional
    Image = None

MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


class ImportView(View):
    number, title, hint = None, "Import", "picture, hand drawing, screenshot or a circuit file"

    def __init__(self, ctx, doc, parent):                              # no Card chrome: the page draws its own soft cards
        self.ctx, self.doc = ctx, doc
        self.card = tk.Frame(parent, bd=0); self.body = self.card
        self.build()
        doc.subscribe(self.on_doc)

    def build(self):
        ctx = self.ctx
        self.main = None; self.usage_text = ""; self._saved_where = None; self.job_id = 0; self.q = queue.Queue(); self.image_bytes = self.image_mime = self.preview = None
        self.busy = False; self.prev_data = None; self.prev_job = None; self.prev_path = None; self.muted = []; self.cards = []
        root = self.card; root.columnconfigure(0, weight=5, uniform="c"); root.columnconfigure(1, weight=3, uniform="c", minsize=380); root.rowconfigure(1, weight=1)
        # ---- header
        self.head = tk.Frame(root); self.head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.h_title = tk.Label(self.head, text="Import & AI", font=ctx.f_title, anchor="w"); self.h_title.pack(side="left", padx=(20, 0), pady=8)
        self.h_sub = tk.Label(self.head, text="", font=ctx.f_small, anchor="w"); self.h_sub.pack(side="left", pady=(4, 0))
        # ---- left: the picture, as large as the window allows
        left = SoftCard(ctx, root, pad=22); left.grid(row=1, column=0, sticky="nsew", padx=(0, 2)); self.cards.append(left); lb = left.body
        lb.columnconfigure(0, weight=1); lb.rowconfigure(1, weight=1)
        self.l_cap = tk.Label(lb, text="Your picture", font=ctx.f_bold, anchor="w"); self.l_cap.grid(row=0, column=0, sticky="w")
        self.l_dbl = tk.Label(lb, text="", font=ctx.f_small, anchor="e"); self.l_dbl.grid(row=0, column=0, sticky="e")
        self.prev_box = tk.Frame(lb, bd=0, highlightthickness=0); self.prev_box.grid(row=1, column=0, sticky="nsew", pady=(10, 14)); self.prev_box.pack_propagate(False); self.prev_box.grid_propagate(False)
        self.lbl_prev = tk.Label(self.prev_box, text="No picture yet\n\nImport or paste a picture of a circuit", font=ctx.f_body, justify="center", cursor="hand2")
        self.lbl_prev.pack(fill="both", expand=True)
        self.lbl_prev.bind("<Double-Button-1>", lambda e: self.enlarge()); self.prev_box.bind("<Configure>", lambda e: self._later_preview())
        # what is sent: the scanned picture (cropped, flat light, black on white, small) or the original; Adjust crop opens the frame editor
        sc = tk.Frame(lb); sc.grid(row=2, column=0, sticky="ew", pady=(0, 10)); self.scan_row = sc; top = tk.Frame(sc); top.pack(fill="x"); self.scan_top = top; self.scan_box = None; self.orig_bytes = self.orig_mime = None; self.scan_info = {}
        self.scan_seg = Segmented(ctx, top, [("Scanned", "scanned"), ("Original", "original")], "scanned" if self.cfg_get("scan_on", True) else "original", self.scan_mode_changed); self.scan_seg.pack(side="left")
        self.btn_crop = Pill(ctx, top, "Adjust crop", self.adjust_crop, "soft", height=32, width=ctx.f_body.measure("Adjust crop") + 40); self.btn_crop.pack(side="left", padx=(10, 0))
        self.btn_crop.tip("Scanned: cropped to the circuit, flat light, dark lines on white (cheaper and clearer for the AI). Original: the picture as it is. Drag the frame to choose the part yourself.")
        self.tune = {}
        for key, icon, tip in (("scan_contrast", "\u25d0", "contrast (harder, blacker lines)"), ("scan_ink", "\u270e", "line strength (keeps fainter pencil lines)")):
            grp = tk.Frame(top); grp.pack(side="left", padx=(10, 0)); self.tune[key] = grp; self.scan_tools = getattr(self, "scan_tools", []) + [grp]
            tk.Label(grp, text=icon, font=ctx.f_bold).pack(side="left", padx=(0, 4)); self.muted.append(grp.winfo_children()[0])
            for sign, d in (("\u2212", -10), ("+", 10)):
                b = Pill(ctx, grp, sign, lambda k=key, d=d: self.nudge_scan(k, d), "soft", height=28, width=30); b.pack(side="left", padx=1)
                b.tip(("Less " if d < 0 else "More ") + tip)
        self.scan_lbl = tk.Label(sc, text="", font=ctx.f_small, anchor="w"); self.scan_lbl.pack(fill="x", pady=(6, 0)); self.muted.append(self.scan_lbl)
        bar = tk.Frame(lb); bar.grid(row=3, column=0, sticky="ew"); bar.columnconfigure(0, weight=1, uniform="b"); bar.columnconfigure(1, weight=1, uniform="b"); self.bar = bar
        self.btn_img = Pill(ctx, bar, "Import picture", self.pick_image, "ink", icon="\u2191"); self.btn_img.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_paste = Pill(ctx, bar, "Paste screenshot", self.paste_image, "soft", icon="\u2398"); self.btn_paste.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        # what the picture becomes, and the instruction that is sent with it
        opt = tk.Frame(lb); opt.grid(row=4, column=0, sticky="ew", pady=(12, 0)); opt.columnconfigure(1, weight=1); self.opt = opt
        l1 = tk.Label(opt, text="Convert to", font=ctx.f_small, anchor="w"); l1.grid(row=0, column=0, sticky="w", padx=(0, 12)); self.muted.append(l1)
        c = self.cfg_get("import_target", "auto"); self.target = tk.StringVar(value=LABELS[c if c in TARGETS else "auto"])
        self.cb_target = ttk.Combobox(opt, state="readonly", values=[LABELS[t] for t in TARGETS], textvariable=self.target, style="Modern.TCombobox", font=ctx.f_body)
        self.cb_target.grid(row=0, column=1, sticky="ew", columnspan=2); self.cb_target.bind("<<ComboboxSelected>>", lambda e: self.target_changed())
        l2 = tk.Label(opt, text="Prompt", font=ctx.f_small, anchor="w"); l2.grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(8, 0)); self.muted.append(l2)
        self.pmode = Segmented(ctx, opt, [("Built-in", "default"), ("My own", "custom")], self.cfg_get("import_mode", "default"), self.set_pmode); self.pmode.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.btn_reset = Pill(ctx, opt, "Reset text", self.reset_prompt, "soft", height=30, width=ctx.f_body.measure("Reset text") + 36); self.btn_reset.grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.pfield = Field(ctx, opt, None, max_lines=7); self.pfield.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.custom = dict(self.cfg_get("import_custom", {}) or {}); self.pfield.hint("Tell the AI what to do with the picture\u2026"); self.pfield_tgt = None
        # ---- right: model, key, convert, result
        right = SoftCard(ctx, root, pad=22); right.grid(row=1, column=1, sticky="nsew", padx=(2, 0)); self.cards.append(right); rb = right.body; self.right = rb
        rb.columnconfigure(0, weight=1)
        def cap(text, row, **kw):
            l = tk.Label(rb, text=text, font=ctx.f_small, anchor="w"); l.grid(row=row, column=0, sticky="w", pady=(10, 3), **kw); self.muted.append(l); return l
        tk.Label(rb, text="AI model", font=ctx.f_bold, anchor="w").grid(row=0, column=0, sticky="w"); self.r_cap = rb.grid_slaves(row=0)[0]
        names = list(PROVIDERS)
        self.prov = tk.StringVar(value=ctx.cfg.get("provider", names[0]))
        if self.prov.get() not in PROVIDERS: self.prov.set(names[0])
        cap("Provider", 1)
        cb = ttk.Combobox(rb, state="readonly", values=names, textvariable=self.prov, style="Modern.TCombobox", font=ctx.f_body); cb.grid(row=2, column=0, sticky="ew")
        cb.bind("<<ComboboxSelected>>", lambda e: self.provider_changed())
        cap("Model", 3)
        self.model = tk.StringVar(); self.cb_model = ttk.Combobox(rb, textvariable=self.model, style="Modern.TCombobox", font=ctx.f_body); self.cb_model.grid(row=4, column=0, sticky="ew")
        self.model_user = False; self._auto_tok = 0; self._auto_job = None
        self.cb_model.bind("<<ComboboxSelected>>", lambda e: self.model_manual()); self.cb_model.bind("<KeyRelease>", lambda e: self.model_manual() if e.keysym not in ("Tab", "Shift_L", "Shift_R") else None)
        self.key_lbl = cap("API key  (paste it: the provider is detected for you)", 5); self.key = tk.StringVar()
        self.key_box = tk.Frame(rb); self.key_box.grid(row=6, column=0, sticky="ew"); self.key_box.columnconfigure(0, weight=1)
        self.key_ent = ttk.Entry(self.key_box, textvariable=self.key, show="\u2022", style="Modern.TEntry", font=ctx.f_body); self.key_ent.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_keypaste = Pill(ctx, self.key_box, "", self.paste_key, "soft", height=34, shape="circle", icon="\u2398"); self.btn_keypaste.grid(row=0, column=1); self.btn_keypaste.tip("Paste the key from the clipboard")
        self.detected = tk.Label(self.key_box, text="", font=ctx.f_small, anchor="w"); self.detected.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.remember = tk.BooleanVar(value=True)
        self.rem_chk = tk.Checkbutton(self.key_box, text="Remember this key on this computer", variable=self.remember, command=self.remember_key, anchor="w", font=ctx.f_small, bd=0, highlightthickness=0)
        self.rem_chk.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0)); self.muted.append(self.rem_chk)
        self.key.trace_add("write", lambda *a: self.key_changed())
        self.base_lbl = cap("Server URL", 7); self.base = tk.StringVar()
        self.base_ent = ttk.Entry(rb, textvariable=self.base, style="Modern.TEntry", font=ctx.f_body); self.base_ent.grid(row=8, column=0, sticky="ew")
        self.help = tk.Label(rb, font=ctx.f_small, wraplength=300, justify="left", anchor="w"); self.help.grid(row=9, column=0, sticky="ew", pady=(10, 4)); self.muted.append(self.help)
        rb.bind("<Configure>", lambda e: self.help.configure(wraplength=max(120, e.width - 8)))
        act = tk.Frame(rb); act.grid(row=10, column=0, sticky="ew", pady=(6, 0)); act.columnconfigure(0, weight=1); self.act = act
        self.btn_convert = Pill(ctx, act, "Convert picture to circuit", self.convert, "ink", height=52, icon="\u2192"); self.btn_convert.grid(row=0, column=0, sticky="ew")
        self.btn_pull = Pill(ctx, act, "Download this model to my PC (Ollama)", self.pull_model, "soft", height=38); self.btn_pull.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.status = Notice(ctx, rb, height=4); self.status.grid(row=11, column=0, sticky="nsew", pady=(12, 0)); rb.rowconfigure(11, weight=1)
        self.status.set("Import a picture, check the model, then press Convert.", "none")
        go = tk.Frame(rb); go.grid(row=12, column=0, sticky="ew", pady=(12, 0)); go.columnconfigure(0, weight=1, uniform="g"); go.columnconfigure(1, weight=1, uniform="g"); self.go = go
        self.go_cap = tk.Label(go, text="Open the result in", font=ctx.f_small, anchor="w"); self.go_cap.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)); self.muted.append(self.go_cap)
        self.btn_logisim = Pill(ctx, go, "Logisim", lambda: self.open_result("digital"), "accent", height=42, icon="\u2192"); self.btn_logisim.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        self.btn_multisim = Pill(ctx, go, "Multisim", lambda: self.open_result("analog"), "accent", height=42, icon="\u2192"); self.btn_multisim.grid(row=1, column=1, sticky="ew", padx=(5, 0))
        self.btn_vlsi = Pill(ctx, go, "Verilog", lambda: self.open_result("vlsi"), "accent", height=42, icon="\u2192"); self.btn_vlsi.grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=(8, 0))
        self.btn_sv = Pill(ctx, go, "SystemVerilog", lambda: self.open_result("systemverilog"), "accent", height=42, icon="\u2192"); self.btn_sv.grid(row=2, column=1, sticky="ew", padx=(5, 0), pady=(8, 0))
        files = tk.Frame(rb); files.grid(row=13, column=0, sticky="ew", pady=(10, 0)); files.columnconfigure(0, weight=1, uniform="f"); files.columnconfigure(1, weight=1, uniform="f"); self.files = files
        self.btn_f1 = Pill(ctx, files, "Open .circ file", lambda: self.open_circuit_file("logisim"), "soft", height=38); self.btn_f1.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.btn_f2 = Pill(ctx, files, "Open .cir file", lambda: self.open_circuit_file("multisim"), "soft", height=38); self.btn_f2.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.btn_f1.tip("A circuit you built in Logisim: you get its JSON and truth table"); self.btn_f2.tip("A SPICE netlist (.cir) exported from Multisim: you get its JSON and DC results")
        self.result_kind = None; self.set_result(None); self.job_target = "auto"; self.repairs = 0; self.job_cfg = None
        self.set_pmode(self.pmode.value, first=True); self.update_convert()
        self.provider_changed(first=True)
        if PROVIDERS[self.prov.get()].local: self.check_ollama()
        ctx.themed.append(self._paint); self._paint()
        ctx.root.after(150, self._poll)

    def _paint(self):
        T = tokens(self.ctx)
        self.card.configure(bg=T["bg"]); self.head.configure(bg=T["card"]); self.ctx.glass.attach(self.card); self.ctx.glass.attach(self.head, 22, "pill", (0, 0, 0, 0))
        self.h_title.configure(bg=T["card"], fg=T["ink"]); self.h_sub.configure(bg=T["card"], fg=T["muted"])
        g = self.ctx.glass
        def under(w):                                                   # every plain frame that shows the page colour gets the backdrop behind it
            for ch in w.winfo_children():
                if ch.winfo_class() == "Frame" and ch not in g.under and str(ch.cget("bg")) == str(T["bg"]): g.attach(ch)
                if ch.winfo_class() == "Frame": under(ch)
        under(self.card)
        for w in (self.bar, self.act, self.go, self.files, self.key_box, self.right, self.opt, self.scan_row, self.scan_top, *self.scan_tools): w.configure(bg=T["card"])
        for w in (self.l_cap, self.r_cap): w.configure(bg=T["card"], fg=T["ink"])
        self.l_dbl.configure(bg=T["card"], fg=T["muted"])
        for w in self.muted: w.configure(bg=T["card"], fg=T["muted"], **({"activebackground": T["card"], "activeforeground": T["muted"], "selectcolor": T["field"]} if w is self.rem_chk else {}))
        self.detected.configure(bg=T["card"], fg=T["accent"])
        self.prev_box.configure(bg=T["field"]); self.lbl_prev.configure(bg=T["field"], fg=T["muted"])

    # ---------------- key ----------------
    def paste_key(self):
        try: text = self.ctx.root.clipboard_get()
        except tk.TclError: self.ctx.say("Paste key", "The clipboard has no text. Copy your API key first."); return
        self.key.set(clean_key(text))

    def key_changed(self):
        """A key was typed or pasted: switch to its service at once (from the prefix), then check it and pick the best model in the background."""
        if getattr(self, "_setting_key", False): return
        k = clean_key(self.key.get())
        if k and k != self.key.get() and detect_provider(k): self._setting_key = True; self.key.set(k); self._setting_key = False
        name = detect_provider(k)
        if name and name != self.prov.get():
            self.prov.set(name); self.provider_changed(keep_key=True)
        self.detected.config(text=(f"\u2713 Detected: {name}  ·  checking the key and looking for the best model\u2026" if name else
                                   (f"This key's shape is not recognised; checking it with {self.prov.get()}\u2026" if len(k) > 12 and not PROVIDERS[self.prov.get()].local else
                                    "This key is not recognised: choose the provider yourself." if len(k) > 12 else "")), fg=tokens(self.ctx)["accent"])
        if self._auto_job: self.ctx.root.after_cancel(self._auto_job)
        self._auto_job = self.ctx.root.after(500, self.auto_detect) if k else None

    def model_manual(self):
        """The user picked or typed a model themselves: keep it from now on (until they change the provider)."""
        self.model_user = True; self.ctx.cfg.setdefault("model_manual", {})[self.prov.get()] = True

    def auto_detect(self):
        """Ask the service for its live model list (background) and fill the model box with the best one."""
        self._auto_job = None; k = clean_key(self.key.get()); name = self.prov.get()
        if not k or PROVIDERS[name].local: return
        self._auto_tok += 1; tok = self._auto_tok; base = self.base.get().strip()
        def work():
            try: self.q.put(("auto", (tok, k, discover(k, name, {name: base} if base else None, PROVIDERS))))
            except Exception: pass
        threading.Thread(target=work, daemon=True).start()

    def apply_auto(self, tok, k, found):
        if tok != self._auto_tok or k != clean_key(self.key.get()): return          # the key changed meanwhile
        if found.provider and found.provider != self.prov.get():
            self.prov.set(found.provider); self.provider_changed(keep_key=True)
        if found.models:
            self.cb_model.configure(values=found.models)
            if not self.model_user or not self.model.get().strip(): self.model.set(found.best)
        activity.log("key", f"key check: {found.message or 'no message'}", "ok" if found.accepted else "warn" if found.accepted is None else "error")
        if found.accepted is not False: self.remember_key()
        if found.message: self.detected.config(text=("\u2713 " if found.accepted else "") + found.message, fg=self.ctx.P["bad"] if found.accepted is False else tokens(self.ctx)["accent"])

    def remember_key(self, quiet=True):
        """Keep (or forget) the key of the chosen service, as the 'Remember' box says. Returns where it went: 'keychain', 'file', '' or None (nothing to do)."""
        p = PROVIDERS[self.prov.get()]; k = clean_key(self.key.get())
        if not p.env or not k: return None
        if not self.remember.get(): secrets.delete_key(p.name); return None
        where = secrets.set_key(p.name, k); activity.log("key", f"key for {p.name} remembered: {where or 'not stored'}", "info" if where else "warn")
        if not quiet or self._saved_where != (p.name, k):
            self._saved_where = (p.name, k)
            if where == "file": self.ctx.toast("Key saved on this computer (private file in your home folder). Install 'keyring' to use the system keychain instead.", "ok")
            elif where == "keychain": self.ctx.toast("Key saved in your computer's keychain.", "ok")
            else: self.ctx.say("Key", "The key could not be saved (the home folder is not writable). It is used for this session only.")
        return where

    def set_result(self, kind):
        """Enable only the button that matches what the AI produced (None: both off)."""
        self.result_kind = kind
        self.btn_logisim.set_enabled(kind == "digital"); self.btn_multisim.set_enabled(kind == "analog")
        self.btn_vlsi.set_enabled(kind == "vlsi"); self.btn_sv.set_enabled(kind == "systemverilog")

    PAGE_OF = {"digital": "logisim", "analog": "multisim", "vlsi": "vlsi", "systemverilog": "systemverilog"}

    def open_result(self, kind):
        if kind == self.result_kind and self.main: self.main.show(self.PAGE_OF[kind])

    # ---------------- what to convert to, and the prompt
    def cfg_get(self, key, default): return self.ctx.cfg.get(key, default)

    def cur_target(self):
        lab = self.target.get()
        return next((t for t in TARGETS if LABELS[t] == lab), "auto")

    def update_convert(self):
        t = self.cur_target()
        self.btn_convert.configure(text="Convert picture to code" if is_code(t) else "Convert picture to circuit")

    def target_changed(self):
        self._store_custom(); self.update_convert(); self._load_custom()

    def _store_custom(self):
        """Remember what was typed for the target that was shown (only when it differs from the built-in text)."""
        t = self.pfield_tgt
        if t is None: return
        text = self.pfield.get().strip()
        if text and text != default_task(t).strip(): self.custom[t] = text
        else: self.custom.pop(t, None)

    def _load_custom(self):
        t = self.cur_target(); self.pfield_tgt = t
        self.pfield.set(self.custom.get(t) or default_task(t))

    def set_pmode(self, mode, first=False):
        self.pmode.set(mode)
        if mode == "custom":
            if first: self._load_custom()
            else: self._load_custom()
            self.pfield.grid(); self.btn_reset.grid()
        else:
            self._store_custom(); self.pfield_tgt = None
            self.pfield.grid_remove(); self.btn_reset.grid_remove()

    def reset_prompt(self):
        self.custom.pop(self.cur_target(), None); self._load_custom()

    def prompt_for(self, target):
        """The instruction sent with the picture: the built-in one of the chosen tab, or the user's own text (the format rules are always added)."""
        text = image_prompt(target, self.pfield.get()) if self.pmode.value == "custom" else image_prompt(target)
        return text + "\n\n" + compact.FORMAT_HELP if tuning.get("compact_answer") and not is_code(target) else text

    def reload(self):
        """Re-read provider / model / URL from the saved settings (called by the Settings page)."""
        p = self.ctx.cfg.get("provider")
        if p in PROVIDERS: self.prov.set(p)
        self.provider_changed()

    def settings(self):
        c = self.ctx.cfg; p = self.prov.get()
        c["provider"] = p; c.setdefault("models", {})[p] = self.model.get(); c.setdefault("bases", {})[p] = self.base.get()
        if self.pmode.value == "custom": self._store_custom()
        c["import_target"] = self.cur_target(); c["import_mode"] = self.pmode.value; c["import_custom"] = dict(self.custom)

    # ---------------- provider ----------------
    def provider_changed(self, first=False, keep_key=False):
        p = PROVIDERS[self.prov.get()]; cfg = self.ctx.cfg
        self.cb_model.configure(values=p.models)
        self.model.set(cfg.get("models", {}).get(p.name) or p.models[0]); self.model_user = bool(cfg.get("model_manual", {}).get(p.name))
        saved = secrets.get_key(p.name) if p.env else ""
        if not keep_key:
            self._setting_key = True; self.key.set(os.environ.get(p.env, "") or saved if p.env else ""); self._setting_key = False
            self.remember.set(True); self.detected.config(text="")
        elif saved and not self.key.get().strip(): self.remember.set(True)
        self.key_lbl.config(text="API key  (paste it: the provider is detected for you)" if p.env else "API key  (not needed for a local model; a pasted key switches the provider)")
        self.base.set(cfg.get("bases", {}).get(p.name) or p.base)
        for w in (self.base_lbl, self.base_ent): (w.grid() if p.show_base else w.grid_remove())
        (self.btn_pull.grid() if p.local else self.btn_pull.grid_remove())
        if p.local and not first: self.check_ollama()
        if p.env and not keep_key and self.key.get().strip(): self.ctx.root.after(600, self.auto_detect)        # a key from the environment or keychain
        self.help.config(text=p.help + ("  (key found in environment)" if p.env and os.environ.get(p.env) else "  (key loaded from your keychain)" if p.env and saved else "") + "  The image is sent to this service.")

    def check_ollama(self):
        base = self.base.get().strip() or PROVIDERS[self.prov.get()].base
        def work():
            try: self.q.put(("models", ollama_models(base)))
            except Exception: self.q.put(("nomodels", base))
        threading.Thread(target=work, daemon=True).start()

    def pull_model(self):
        m, base = self.model.get().strip(), self.base.get().strip() or PROVIDERS[self.prov.get()].base
        if not m: self.ctx.say("Download model", "Enter a model name first."); return
        self.btn_pull.set_enabled(False); self.status.set(f"Starting download of {m}…", "info")
        def work():
            try: ollama_pull(base, m, lambda s: self.q.put(("info", s))); self.q.put(("pulled", m))
            except Exception as e: self.q.put(("err", str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ---------------- image ----------------
    def show_preview(self, data, path=None):
        self.prev_data, self.prev_path = data, path; self._render_preview()

    def enlarge(self):
        if not self.prev_data: return
        PictureViewer(self.ctx, self.prev_data, os.path.basename(self.prev_path) if self.prev_path else "Picture")

    def _later_preview(self):
        if self.prev_job: self.ctx.root.after_cancel(self.prev_job)
        self.prev_job = self.ctx.root.after(120, self._render_preview)

    def _render_preview(self):
        self.prev_job = None; data, path = self.prev_data, getattr(self, "prev_path", None)
        if not data: return
        W, H = max(160, self.prev_box.winfo_width() - 4), max(120, self.prev_box.winfo_height() - 4)
        try:
            self.preview = self._thumb(data, W, H)
            self.lbl_prev.config(image=self.preview, text="")
        except Exception:
            self.preview = None
            self.lbl_prev.config(image="", text=(os.path.basename(path) if path else "image") + "\n(preview not available;\nit will still be sent)")

    @staticmethod
    def _thumb(data, W, H):
        """A Tk image that fits W x H. Pillow decodes any format and hands Tk a PNG (works even without ImageTk);
        without Pillow Tk itself can show PNG and GIF."""
        if Image is not None:
            im = Image.open(io.BytesIO(data)); im.load()
            if im.mode not in ("RGB", "RGBA"): im = im.convert("RGBA")
            f = min(W / im.width, H / im.height, 3.0)                  # shrink to fit, or enlarge small pictures up to 3x
            if f != 1: im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS if f < 1 else Image.BICUBIC)
            out = io.BytesIO(); im.save(out, "PNG")
            return tk.PhotoImage(data=base64.b64encode(out.getvalue()))
        img = tk.PhotoImage(data=base64.b64encode(data)); f = max(1, math.ceil(img.width() / W), math.ceil(img.height() / H))
        return img.subsample(f, f)

    @staticmethod
    def prepare(data, mime):
        """Shrink very large images (needs Pillow); returns (bytes, mime)."""
        if Image is None: return data, mime
        try:
            im = Image.open(io.BytesIO(data))
            if max(im.size) <= 2400 and len(data) < 4_000_000: return data, mime
            im.thumbnail((2400, 2400)); out = io.BytesIO()
            if im.mode in ("RGBA", "P", "LA"): im.save(out, "PNG"); return out.getvalue(), "image/png"
            im.convert("RGB").save(out, "JPEG", quality=90); return out.getvalue(), "image/jpeg"
        except Exception: return data, mime

    # ---------------- scan: what is really sent ----------------
    def set_source(self, data, mime):
        """A new picture: keep the original, forget the old crop, build what will be sent."""
        self.orig_bytes, self.orig_mime, self.scan_box = data, mime, None; self.rebuild_scan()

    def rebuild_scan(self):
        """Make the picture that will be sent (scanned or original, as the switch says) and show it."""
        if not self.orig_bytes: return
        if self.scan_seg.value == "scanned" and scan.Image is not None:
            t0 = time.time(); b, m, info = scan.prepare(self.orig_bytes, self.orig_mime, scan.from_cfg(self.ctx.cfg), self.scan_box)
            if info.get("scanned"): activity.log("scan", f"scanned in {time.time() - t0:.1f} s: {info['from'][0]}x{info['from'][1]} -> {info['size'][0]}x{info['size'][1]} px, {len(self.orig_bytes) // 1024:,} KB -> {info['bytes'] // 1024:,} KB" + ("  (manual crop)" if self.scan_box else "  (automatic crop)"), "ok")
            else: activity.log("scan", f"scan failed, the original is sent: {info.get('why')}", "warn")
        else: b, m, info = self.orig_bytes, self.orig_mime, {"scanned": False}
        self.image_bytes, self.image_mime, self.scan_info = b, m, info
        self.show_preview(b, self.prev_path)
        if info.get("scanned"): txt = f"Sent: scanned, {info['size'][0]} × {info['size'][1]} px, {max(1, info['bytes'] // 1024)} KB"
        elif self.scan_seg.value == "scanned": txt = "Scan not possible here: the original is sent" + (f" ({info['why']})" if info.get("why") else "")
        else: txt = f"Sent: the original, {max(1, len(b) // 1024)} KB"
        self.scan_lbl.config(text=txt)

    def nudge_scan(self, key, d):
        """The + / - buttons next to Adjust crop: change contrast or line strength by 10 and rebuild what is sent."""
        v = max(0, min(100, int(self.ctx.cfg.get(key, 50)) + d)); self.ctx.cfg[key] = v; self.ctx.save_cfg()
        if self.scan_seg.value != "scanned": self.scan_seg.set("scanned"); self.ctx.cfg["scan_on"] = True
        self.rebuild_scan(); name = "Contrast" if key == "scan_contrast" else "Line strength"
        self.scan_lbl.config(text=f"{name} {v}  ·  " + self.scan_lbl.cget("text"))

    def scan_mode_changed(self, mode):
        self.scan_seg.set(mode); self.ctx.cfg["scan_on"] = mode == "scanned"; self.ctx.save_cfg(); self.rebuild_scan()

    def scan_changed(self):
        """A scan setting was changed in Settings: follow it."""
        self.scan_seg.set("scanned" if self.ctx.cfg.get("scan_on", True) else "original"); self.rebuild_scan()

    def adjust_crop(self):
        if self._blocked() or not self.orig_bytes: return
        if scan.Image is None: self.ctx.say("Crop", "Cropping needs Pillow (pip install pillow)."); return
        from vibesimulation.workspaces.ai_import.ui.crop_dialog import CropDialog
        d = CropDialog(self.ctx, self.orig_bytes, self.scan_box, scan.from_cfg(self.ctx.cfg)); d.wait_window()
        if d.result is None: return
        self.scan_box = d.result
        if self.scan_seg.value != "scanned": self.scan_seg.set("scanned"); self.ctx.cfg["scan_on"] = True; self.ctx.save_cfg()
        self.rebuild_scan()

    def load_image(self, p):
        if self._blocked(): return
        ext = os.path.splitext(p)[1].lower()
        if ext not in MIMES: self.ctx.say("Image", "Please use a PNG, JPG, WEBP or GIF image."); return
        data = Path(p).read_bytes(); activity.log("import", f"picture loaded: {os.path.basename(p)} ({len(data) // 1024:,} KB, {ext[1:]})")
        self.prev_path = p; self.set_source(*self.prepare(data, MIMES[ext])); self.set_result(None)
        self.status.set(f"Loaded {os.path.basename(p)} ({len(data) // 1024} KB). Now press Convert.", "info")

    def _lock(self, on):
        """While the AI is working no other picture or file may be loaded (it would replace what is being converted)."""
        self.busy = on
        for b in (self.btn_img, self.btn_paste, self.btn_f1, self.btn_f2): b.set_enabled(not on)
        self.btn_convert.configure(text="Stop" if on else ("Convert picture to code" if is_code(self.cur_target()) else "Convert picture to circuit"))
        self.cb_target.configure(state="disabled" if on else "readonly")

    def _blocked(self):
        if self.busy: self.ctx.say("Please wait", "The AI is still converting the current picture. You can import another one when it is finished."); return True
        return False

    def pick_image(self):
        if self._blocked(): return
        p = self.ctx.choose_file("open", "Choose a circuit image", list(MIMES))
        if p: self.load_image(p)

    def paste_image(self):
        if self._blocked(): return
        try:
            from PIL import ImageGrab
            im = ImageGrab.grabclipboard()
        except Exception as e:
            self.ctx.say("Paste screenshot", "Pasting needs Pillow (pip install pillow) and, on Linux, xclip or wl-clipboard.\nOr save the screenshot as a file and use Import image.\n\n" + str(e)); return
        if im is None or isinstance(im, list):
            self.ctx.say("Paste screenshot", "No image on the clipboard. Take a screenshot to the clipboard first."); return
        out = io.BytesIO(); im.save(out, "PNG"); data = out.getvalue(); activity.log("import", f"screenshot pasted from the clipboard ({len(data) // 1024:,} KB)")
        self.prev_path = None; self.set_source(*self.prepare(data, "image/png")); self.set_result(None)
        self.status.set("Screenshot pasted from the clipboard. Now press Convert.", "info")

    # ---------------- AI ----------------
    def end_job(self, ok, text):
        if getattr(self, "jid_act", None): activity.LOG.end(self.jid_act, ok, text); self.jid_act = None

    def stop(self, why="Stopped"):
        """Give up on the running conversion (its late answer is ignored)."""
        self.job_id += 1; self.end_job(False, why + " by the user" if why == "Stopped" else why); self._lock(False); self.status.set("Stopped. Nothing was changed. Pick another model or try again.", "info")

    def convert(self):
        if self.busy: return self.stop()
        if not self.image_bytes: self.ctx.say("Convert", "Import or paste a circuit image first."); return
        name, m, k, base = self.prov.get(), self.model.get().strip(), self.key.get().strip(), self.base.get().strip()
        prov = PROVIDERS[name]
        if not m: self.ctx.say("Convert", "Enter a model name."); return
        if prov.env and not k: self.ctx.say("Convert", f"Enter your API key for {name}.\n{prov.help}"); return
        self.remember_key(); activity.secret(k)
        target = self.cur_target(); prompt = self.prompt_for(target); self.job_target, self.repairs, self.job_cfg = target, 0, (name, m, k, base)
        self.set_result(None); self._lock(True); self.status.set(f"Asking {m}… (gives up after {providers.TIMEOUT // 60} minutes; press Stop to cancel)", "info"); self.usage_text = ""
        img, mime = self.image_bytes, self.image_mime; want_json = not is_code(target)
        self.job_id += 1; jid = self.job_id; self.t_start = time.time()
        self.jid_act = activity.LOG.begin(f"converting with {name} / {m}", source="import")
        activity.log("import", f"Convert pressed: {name}, model {m}, to {LABELS[target]}; prompt {len(prompt):,} characters; picture {len(img) // 1024:,} KB ({mime}, {'scanned' if self.scan_info.get('scanned') else 'original'}); "
                               f"short answer {'on' if tuning.get('compact_answer') and want_json else 'off'}; thinking limit {'on' if tuning.get('limit_reasoning') else 'off'}")
        def work():
            usage.context("picture"); usage.clear_last()
            def put(kind, val):
                if jid == self.job_id: self.q.put((kind, val))                       # stopped meanwhile: drop the late answer
            try:
                text, used = call_with_fallback(name, m, k, base, lambda mm: ask_model(name, mm, k, img, mime, base, prompt, want_json), PROVIDERS)
                if used != m: put("model", (m, used))
                put("usage", usage.summary(usage.last()))
                put("ok", text)
            except Exception as e: put("err", str(e) + explain_error(name, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def open_circuit_file(self, which):
        if self._blocked(): return
        exts = [".circ", ".json"] if which == "logisim" else [".cir", ".sp", ".net", ".spice", ".ckt", ".json", ".ms14", ".txt"]
        p = self.ctx.choose_file("open", "Choose a Logisim circuit" if which == "logisim" else "Choose a Multisim / SPICE netlist", exts)
        if not p: return
        self.set_result(None)
        try: kind, text, notes = load_file(p)
        except Exception as e:
            self.status.set(f"Could not open {os.path.basename(p)}: {e}", "bad"); return
        self.prev_data = None
        self.lbl_prev.config(image="", text=f"{os.path.basename(p)}\n{'Logisim circuit' if kind == 'digital' else 'Multisim (SPICE) circuit'} opened")
        self.finish(text, source=os.path.basename(p), notes=notes)

    def finish(self, val, source=None, notes=()):
        """Put a circuit (the model's answer, or a file) into the Logisim or Multisim document, whichever kind of circuit it is."""
        try: raw = extract_json(compact.to_json_text(val))
        except Exception as e:
            activity.log("import", f"the answer could not be read as a circuit ({e}). Start of the answer: {val.strip()[:200]!r}", "error")
            self.doc.load_text(val); self.status.set(f"The answer was not usable ({e}). It is in the Logisim JSON box so you can fix it.", "bad"); return
        kind = classify(raw); activity.log("import", f"the answer is a {kind} circuit", "ok")
        if kind == "analog":
            nl, errs = aparse(raw)
            if nl is not None and not errs: errs = nl.validate()
            text = adumps(nl) if nl is not None else json.dumps(raw, indent=2)
            self.main.adoc.load_text(text) if self.main else None
            if errs: self.status.set("Analog circuit found, but it needs fixing: " + "; ".join(errs[:3]) + "  Open it in Multisim to correct the JSON." + self._notes(notes), "bad")
            elif source: self.status.set(f"Opened {source}: an analog circuit with {len(nl.parts)} parts. The JSON and the DC results are ready; press Open in Multisim." + self._notes(notes), "bad" if notes else "ok")
            else: self.status.set("Done: this is an analog circuit. Check it against your drawing, then press Open in Multisim." + self._notes(notes), "ok")
        elif kind == "digital" and isinstance(raw.get("circuits"), dict):
            self.doc.load_project(json.dumps(raw)); self.doc.set_inputs({})
            errs = [] if self.doc.valid else self.doc.errors
            n = len(self.doc.circuit_names())
            if errs: self.status.set(f"Project with {n} circuits found, but circuit '{self.doc.cur}' needs fixing: " + "; ".join(errs[:3]) + self._notes(notes), "bad")
            else: self.status.set((f"Opened {source}: " if source else "Done: ") + f"a project with {n} circuits (tabs above the circuit view). Press Open in Logisim." + self._notes(notes), "bad" if notes else "ok")
        elif kind == "digital":
            circuit, errs = parse(raw)
            if circuit is not None and not errs: errs = circuit.validate()
            text = dumps(circuit) if circuit is not None else json.dumps(raw, indent=2)
            self.doc.load_text(text); self.doc.set_inputs({})
            if errs: self.status.set("Logic circuit found, but it needs fixing: " + "; ".join(errs[:3]) + "  Open it in Logisim to correct the JSON." + self._notes(notes), "bad")
            elif source: self.status.set(f"Opened {source}: a logic circuit with {len(circuit.inputs)} inputs, {len(circuit.components)} parts and {len(circuit.outputs)} outputs. The JSON and the truth table are ready; press Open in Logisim." + self._notes(notes), "bad" if notes else "ok")
            else: self.status.set("Done: this is a logic circuit. Check it against your drawing, then press Open in Logisim." + self._notes(notes), "ok")
        else:
            self.doc.load_text(val); self.status.set("The answer was not a circuit I understand. It is in the Logisim JSON box so you can fix it.", "bad"); return
        self.set_result(kind)
        if self.main and self.ctx.cfg.get("auto_open", False) and not errs: self.main.show("logisim" if kind == "digital" else "multisim")

    def finish_code(self, val):
        """The AI answered with Verilog / SystemVerilog: compile it (asking the model to fix mistakes), then make it the project of that tab."""
        t = self.job_target; doc = self.main.vdoc if t == "vlsi" else self.main.sdoc; name = LABELS[t].split(" (")[0]
        try: code = extract_code(val)
        except ValueError as e: self.status.set(f"The answer had no code in it ({e}).", "bad"); return
        circuits = {n: e["text"] for n, e in doc.circuits.items()}; circuits[doc.cur] = doc.text
        res = doc.compile(code, circuits, doc.cur); errs = [f"line {ln}: {m}" for ln, m in res.errors]
        if errs and self.repairs < 2 and self.job_cfg:
            self.repairs += 1; n, m, k, base = self.job_cfg; self._lock(True)
            self.status.set(f"The code had {len(errs)} problem{'s' if len(errs) != 1 else ''}; asking the AI to fix it (try {self.repairs} of 2)\u2026", "info")
            def work():
                try:
                    text, used = call_with_fallback(n, m, k, base, lambda mm: chat_model(n, mm, k, code_system(t), repair_prompt(t, code, errs), base, False), PROVIDERS)
                    if used != m: self.q.put(("model", (m, used)))
                    self.q.put(("ok", text))
                except Exception as e: self.q.put(("err", str(e) + explain_error(n, str(e))))
            threading.Thread(target=work, daemon=True).start(); return
        if errs:                                                       # still wrong: show it in the editor with the faulty lines marked, so it can be fixed by hand
            ed = self.main.pages[t].views["verilog"]; txt = code.rstrip("\n"); ed.show_text(txt); ed.flush_text(txt)
            self.status.set(f"{name} code received, but it does not compile yet: " + "; ".join(errs[:3]) + f"  Open it in {name} to correct it.", "bad"); return
        doc.new_blank(code); mods = len(res.circuits)
        self.status.set(f"Done: {name} code with {mods} module{'s' if mods != 1 else ''}. Check it against your picture, then press Open in {name}." + self._notes((self.usage_text,) if self.usage_text else ()), "ok")
        self.set_result(t)
        if self.ctx.cfg.get("auto_open", False): self.main.show(self.PAGE_OF[t])

    @staticmethod
    def _notes(notes): return ("\n" + "\n".join(notes)) if notes else ""

    def _watch(self):
        """A conversion that has gone on far longer than the service's own time limit is stopped (the service or the network is stuck)."""
        if not (self.busy and self.job_cfg): return
        limit = 1900 if PROVIDERS[self.job_cfg[0]].local else providers.TIMEOUT + 30
        if time.time() - getattr(self, "t_start", time.time()) > limit:
            activity.log("import", f"watchdog: no answer after {limit} s, giving up", "error")
            self.stop("Gave up"); self.status.set(f"No answer after {limit // 60} minutes, so I stopped waiting. The service or model is busy or stuck: choose another model, or see the Activity page (</>).", "bad")

    def _poll(self):
        self._watch()
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "info": self.status.set(val, "info"); continue
                if kind == "auto": self.apply_auto(*val); continue
                if kind == "usage": self.usage_text = val; continue
                if kind == "model":
                    old, new = val; self.model.set(new); self.status.set(f"{old} is not available (any more); using {new} instead.", "info")
                    if self.job_cfg: self.job_cfg = (self.job_cfg[0], new, *self.job_cfg[2:])
                    continue
                local = PROVIDERS[self.prov.get()].local
                if kind == "models":
                    if local:
                        have = val + [m for m in PROVIDERS[self.prov.get()].models if m not in val]
                        self.cb_model.configure(values=have)
                        if val and self.model.get() not in val: self.model.set(val[0])
                        self.status.set("Ollama is running. Installed: " + (", ".join(val) or "no models yet - press Download."), "ok")
                    continue
                if kind == "nomodels":
                    if local: self.status.set(f"Ollama was not found at {val}. Install it from ollama.com, start it, then press Download. Cloud providers still work.", "bad")
                    continue
                if kind == "pulled":
                    self.btn_pull.set_enabled(True); self.status.set(f"{val} is ready. Import an image and press Convert.", "ok"); self.check_ollama(); continue
                self._lock(False); self.btn_pull.set_enabled(True)
                if kind == "err": self.end_job(False, "failed"); activity.log("import", "conversion failed: " + val.split("\n")[0][:300], "error"); self.status.set("Failed: " + val, "bad"); continue
                self.end_job(True, f"answer received ({len(val):,} characters)")
                self.finish_code(val) if is_code(self.job_target) else self.finish(val, notes=(self.usage_text,) if self.usage_text else ()); self.usage_text = ""
        except queue.Empty:
            pass
        self.ctx.root.after(150, self._poll)
