"""Box 1: pick an image and let an AI model turn it into circuit JSON."""
import base64
import io
import json
import math
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..engine import PROVIDERS, ask_model, explain_error, extract_json, ollama_models, ollama_pull
from ..engine import secrets
from ..engine.key_detect import clean_key, detect_provider
from ...multisim.engine.netlist import dumps as adumps, parse as aparse
from ....core.serializer import dumps, parse
from ....imports import classify, load_file
from ....ui.widgets import Btn, Notice
from .skin import Pill, SoftCard, tokens
from .viewer import PictureViewer
from ....ui.views.base import View

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
        self.main = None; self.q = queue.Queue(); self.image_bytes = self.image_mime = self.preview = None
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
        bar = tk.Frame(lb); bar.grid(row=2, column=0, sticky="ew"); bar.columnconfigure(0, weight=1, uniform="b"); bar.columnconfigure(1, weight=1, uniform="b"); self.bar = bar
        self.btn_img = Pill(ctx, bar, "Import picture", self.pick_image, "ink", icon="\u2191"); self.btn_img.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_paste = Pill(ctx, bar, "Paste screenshot", self.paste_image, "soft", icon="\u2398"); self.btn_paste.grid(row=0, column=1, sticky="ew", padx=(6, 0))
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
        self.key_lbl = cap("API key  (paste it: the provider is detected for you)", 5); self.key = tk.StringVar()
        self.key_box = tk.Frame(rb); self.key_box.grid(row=6, column=0, sticky="ew"); self.key_box.columnconfigure(0, weight=1)
        self.key_ent = ttk.Entry(self.key_box, textvariable=self.key, show="\u2022", style="Modern.TEntry", font=ctx.f_body); self.key_ent.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_keypaste = Pill(ctx, self.key_box, "", self.paste_key, "soft", height=34, shape="circle", icon="\u2398"); self.btn_keypaste.grid(row=0, column=1); self.btn_keypaste.tip("Paste the key from the clipboard")
        self.detected = tk.Label(self.key_box, text="", font=ctx.f_small, anchor="w"); self.detected.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.remember = tk.BooleanVar(value=False)
        self.rem_chk = tk.Checkbutton(self.key_box, text="Remember this key in my computer's keychain", variable=self.remember, anchor="w", font=ctx.f_small, bd=0, highlightthickness=0)
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
        self.btn_logisim = Pill(ctx, go, "Open in Logisim", lambda: self.open_result("digital"), "accent", icon="\u2192"); self.btn_logisim.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.btn_multisim = Pill(ctx, go, "Open in Multisim", lambda: self.open_result("analog"), "accent", icon="\u2192"); self.btn_multisim.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        files = tk.Frame(rb); files.grid(row=13, column=0, sticky="ew", pady=(10, 0)); files.columnconfigure(0, weight=1, uniform="f"); files.columnconfigure(1, weight=1, uniform="f"); self.files = files
        self.btn_f1 = Pill(ctx, files, "Open .circ file", lambda: self.open_circuit_file("logisim"), "soft", height=38); self.btn_f1.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.btn_f2 = Pill(ctx, files, "Open .cir file", lambda: self.open_circuit_file("multisim"), "soft", height=38); self.btn_f2.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.btn_f1.tip("A circuit you built in Logisim: you get its JSON and truth table"); self.btn_f2.tip("A SPICE netlist (.cir) exported from Multisim: you get its JSON and DC results")
        self.result_kind = None; self.set_result(None)
        self.provider_changed(first=True)
        if PROVIDERS[self.prov.get()].local: self.check_ollama()
        ctx.themed.append(self._paint); self._paint()
        ctx.root.after(150, self._poll)

    def _paint(self):
        T = tokens(self.ctx); P = self.ctx.P
        self.card.configure(bg=T["bg"]); self.head.configure(bg=T["card"]); self.ctx.glass.attach(self.card); self.ctx.glass.attach(self.head, 22, "pill", (0, 0, 0, 0))
        self.h_title.configure(bg=T["card"], fg=T["ink"]); self.h_sub.configure(bg=T["card"], fg=T["muted"])
        g = self.ctx.glass
        def under(w):                                                   # every plain frame that shows the page colour gets the backdrop behind it
            for ch in w.winfo_children():
                if ch.winfo_class() == "Frame" and ch not in g.under and str(ch.cget("bg")) == str(T["bg"]): g.attach(ch)
                if ch.winfo_class() == "Frame": under(ch)
        under(self.card)
        for w in (self.bar, self.act, self.go, self.files, self.key_box, self.right): w.configure(bg=T["card"])
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
        """A key was typed or pasted: find out which service it belongs to and switch to it."""
        if getattr(self, "_setting_key", False): return
        k = clean_key(self.key.get())
        if k and k != self.key.get() and detect_provider(k): self._setting_key = True; self.key.set(k); self._setting_key = False
        name = detect_provider(k)
        if name is None:
            self.detected.config(text=("This key is not recognised: choose the provider yourself." if len(k) > 12 else "")); return
        if name != self.prov.get():
            self.prov.set(name); self.provider_changed(keep_key=True)
        self.detected.config(text=f"\u2713 Detected: {name}")

    def set_result(self, kind):
        """Enable only the button that matches what the AI produced (None: both off)."""
        self.result_kind = kind
        self.btn_logisim.set_enabled(kind == "digital"); self.btn_multisim.set_enabled(kind == "analog")

    def open_result(self, kind):
        if kind == self.result_kind and self.main: self.main.show("logisim" if kind == "digital" else "multisim")

    def reload(self):
        """Re-read provider / model / URL from the saved settings (called by the Settings page)."""
        p = self.ctx.cfg.get("provider")
        if p in PROVIDERS: self.prov.set(p)
        self.provider_changed()

    def settings(self):
        c = self.ctx.cfg; p = self.prov.get()
        c["provider"] = p; c.setdefault("models", {})[p] = self.model.get(); c.setdefault("bases", {})[p] = self.base.get()

    # ---------------- provider ----------------
    def provider_changed(self, first=False, keep_key=False):
        p = PROVIDERS[self.prov.get()]; cfg = self.ctx.cfg
        self.cb_model.configure(values=p.models)
        self.model.set(cfg.get("models", {}).get(p.name) or p.models[0])
        saved = secrets.get_key(p.name) if p.env else ""
        if not keep_key:
            self._setting_key = True; self.key.set(os.environ.get(p.env, "") or saved if p.env else ""); self._setting_key = False
            self.remember.set(bool(saved)); self.detected.config(text="")
        elif saved and not self.key.get().strip(): self.remember.set(True)
        self.key_lbl.config(text="API key  (paste it: the provider is detected for you)" if p.env else "API key  (not needed for a local model; a pasted key switches the provider)")
        self.base.set(cfg.get("bases", {}).get(p.name) or p.base)
        for w in (self.base_lbl, self.base_ent): (w.grid() if p.show_base else w.grid_remove())
        (self.btn_pull.grid() if p.local else self.btn_pull.grid_remove())
        if p.local and not first: self.check_ollama()
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

    def load_image(self, p):
        if self._blocked(): return
        ext = os.path.splitext(p)[1].lower()
        if ext not in MIMES: self.ctx.say("Image", "Please use a PNG, JPG, WEBP or GIF image."); return
        data = Path(p).read_bytes()
        self.image_bytes, self.image_mime = self.prepare(data, MIMES[ext]); self.show_preview(data, p); self.set_result(None)
        self.status.set(f"Loaded {os.path.basename(p)} ({len(data) // 1024} KB). Now press Convert.", "info")

    def _lock(self, on):
        """While the AI is working no other picture or file may be loaded (it would replace what is being converted)."""
        self.busy = on
        for b in (self.btn_img, self.btn_paste, self.btn_f1, self.btn_f2, self.btn_convert): b.set_enabled(not on)

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
        out = io.BytesIO(); im.save(out, "PNG"); data = out.getvalue()
        self.image_bytes, self.image_mime = self.prepare(data, "image/png"); self.show_preview(data); self.set_result(None)
        self.status.set("Screenshot pasted from the clipboard. Now press Convert.", "info")

    # ---------------- AI ----------------
    def convert(self):
        if self.busy: return
        if not self.image_bytes: self.ctx.say("Convert", "Import or paste a circuit image first."); return
        name, m, k, base = self.prov.get(), self.model.get().strip(), self.key.get().strip(), self.base.get().strip()
        prov = PROVIDERS[name]
        if not m: self.ctx.say("Convert", "Enter a model name."); return
        if prov.env and not k: self.ctx.say("Convert", f"Enter your API key for {name}.\n{prov.help}"); return
        if prov.env:
            if self.remember.get():
                if not secrets.set_key(name, k): self.ctx.say("Keychain", "The key could not be stored. Install the optional package with:  pip install keyring\nThe key is used for this session only.")
            else: secrets.delete_key(name)
        self.set_result(None); self._lock(True); self.status.set(f"Asking {m}… (can take up to a minute)", "info")
        img, mime = self.image_bytes, self.image_mime
        def work():
            try: self.q.put(("ok", ask_model(name, m, k, img, mime, base)))
            except Exception as e: self.q.put(("err", str(e) + explain_error(name, str(e))))
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
        try: raw = extract_json(val)
        except Exception as e:
            self.doc.load_text(val); self.status.set(f"The answer was not usable ({e}). It is in the Logisim JSON box so you can fix it.", "bad"); return
        kind = classify(raw)
        if kind == "analog":
            nl, errs = aparse(raw)
            if nl is not None and not errs: errs = nl.validate()
            text = adumps(nl) if nl is not None else json.dumps(raw, indent=2)
            self.main.adoc.load_text(text) if self.main else None
            if errs: self.status.set("Analog circuit found, but it needs fixing: " + "; ".join(errs[:3]) + "  Open it in Multisim to correct the JSON." + self._notes(notes), "bad")
            elif source: self.status.set(f"Opened {source}: an analog circuit with {len(nl.parts)} parts. The JSON and the DC results are ready; press Open in Multisim." + self._notes(notes), "bad" if notes else "ok")
            else: self.status.set("Done: this is an analog circuit. Check it against your drawing, then press Open in Multisim.", "ok")
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
            else: self.status.set("Done: this is a logic circuit. Check it against your drawing, then press Open in Logisim.", "ok")
        else:
            self.doc.load_text(val); self.status.set("The answer was not a circuit I understand. It is in the Logisim JSON box so you can fix it.", "bad"); return
        self.set_result(kind)
        if self.main and self.ctx.cfg.get("auto_open", False) and not errs: self.main.show("logisim" if kind == "digital" else "multisim")

    @staticmethod
    def _notes(notes): return ("\n" + "\n".join(notes)) if notes else ""

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "info": self.status.set(val, "info"); continue
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
                if kind == "err": self.status.set("Failed: " + val, "bad"); continue
                self.finish(val)
        except queue.Empty:
            pass
        self.ctx.root.after(150, self._poll)
