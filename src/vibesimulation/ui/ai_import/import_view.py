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

from ...ai import PROVIDERS, ask_model, explain_error, extract_json, ollama_models, ollama_pull
from ...analog.netlist import dumps as adumps, parse as aparse
from ...core.serializer import dumps, parse
from ...imports import classify, load_file
from ..widgets import Btn, Notice
from ..views.base import View

try:
    from PIL import Image
except Exception:                      # Pillow is optional
    Image = None

MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


class ImportView(View):
    number, title, hint = None, "Import", "picture, hand drawing, screenshot or a circuit file"

    def build(self):
        ctx = self.ctx
        self.main = None; self.q = queue.Queue(); self.image_bytes = self.image_mime = self.preview = None
        self.muted = []
        b = self.body; b.columnconfigure(0, weight=1); b.rowconfigure(1, weight=3)
        self.left = self.right = b
        def cap(text, row, col=0, span=1):
            l = tk.Label(b, text=text, font=ctx.f_small, anchor="w"); l.grid(row=row, column=col, columnspan=span, sticky="w", pady=(10, 3)); self.muted.append(l); return l
        top = tk.Frame(b); top.grid(row=0, column=0, sticky="ew"); top.columnconfigure(0, weight=1, uniform="t"); top.columnconfigure(1, weight=1, uniform="t"); self.top = top
        self.btn_img = Btn(ctx, top, "Import image…", self.pick_image, "primary"); self.btn_img.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_paste = Btn(ctx, top, "Paste screenshot", self.paste_image, "secondary"); self.btn_paste.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.busy = False
        self.btn_f1 = Btn(ctx, top, "Open Logisim file (.circ)…", lambda: self.open_circuit_file("logisim"), "secondary"); self.btn_f1.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        self.btn_f2 = Btn(ctx, top, "Open Multisim file (.cir)…", lambda: self.open_circuit_file("multisim"), "secondary"); self.btn_f2.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))
        self.btn_f1.tip("A circuit you built in Logisim: you get its JSON and truth table"); self.btn_f2.tip("A SPICE netlist (.cir) exported from Multisim: you get its JSON and DC results")
        self.prev_box = tk.Frame(b, highlightthickness=1, height=190); self.prev_box.grid(row=1, column=0, sticky="nsew", pady=(10, 0)); self.prev_box.pack_propagate(False); self.prev_box.grid_propagate(False)
        self.lbl_prev = tk.Label(self.prev_box, text="No image yet\nImport or paste a picture of a circuit", font=ctx.f_small, justify="center"); self.lbl_prev.pack(fill="both", expand=True)
        self.prev_data = None; self.prev_job = None
        self.prev_box.bind("<Configure>", lambda e: self._later_preview())
        names = list(PROVIDERS)
        self.prov = tk.StringVar(value=ctx.cfg.get("provider", names[0]))
        if self.prov.get() not in PROVIDERS: self.prov.set(names[0])
        pm = tk.Frame(b); pm.grid(row=3, column=0, sticky="ew"); pm.columnconfigure(0, weight=1, uniform="p"); pm.columnconfigure(1, weight=1, uniform="p"); self.pm = pm
        cap("AI model provider", 2); self.model_cap = cap("Model name", 2); self.model_cap.grid_forget()
        l1 = tk.Label(pm, text="AI model provider", font=ctx.f_small, anchor="w"); l1.grid(row=0, column=0, sticky="w", pady=(0, 3)); self.muted.append(l1)
        l2 = tk.Label(pm, text="Model name", font=ctx.f_small, anchor="w"); l2.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 3)); self.muted.append(l2)
        for w in b.grid_slaves(row=2): w.destroy()
        self.muted = [m for m in self.muted if m.winfo_exists()]
        cb = ttk.Combobox(pm, state="readonly", values=names, textvariable=self.prov, style="Modern.TCombobox", font=ctx.f_body)
        cb.grid(row=1, column=0, sticky="ew"); cb.bind("<<ComboboxSelected>>", lambda e: self.provider_changed())
        self.model = tk.StringVar(); self.cb_model = ttk.Combobox(pm, textvariable=self.model, style="Modern.TCombobox", font=ctx.f_body)
        self.cb_model.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.key_lbl = cap("API key", 4); self.key = tk.StringVar()
        self.key_ent = ttk.Entry(b, textvariable=self.key, show="•", style="Modern.TEntry", font=ctx.f_body); self.key_ent.grid(row=5, column=0, sticky="ew")
        self.base_lbl = cap("Server URL", 6); self.base = tk.StringVar()
        self.base_ent = ttk.Entry(b, textvariable=self.base, style="Modern.TEntry", font=ctx.f_body); self.base_ent.grid(row=7, column=0, sticky="ew")
        self.help = tk.Label(b, font=ctx.f_small, wraplength=300, justify="left", anchor="w"); self.help.grid(row=8, column=0, sticky="ew", pady=(8, 8)); self.muted.append(self.help)
        b.bind("<Configure>", lambda e: self.help.configure(wraplength=max(120, e.width - 8)))
        act = tk.Frame(b); act.grid(row=9, column=0, sticky="new"); act.columnconfigure(0, weight=1); self.act = act
        self.btn_convert = Btn(ctx, act, "Convert image to circuit   ▶", self.convert, "primary"); self.btn_convert.grid(row=0, column=0, sticky="ew")
        self.btn_pull = Btn(ctx, act, "⬇  Download this model to my PC (Ollama)", self.pull_model, "secondary", pady=5); self.btn_pull.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.status = Notice(ctx, b, height=3); self.status.grid(row=10, column=0, sticky="nsew", pady=(10, 0)); b.rowconfigure(10, weight=1)
        self.status.set("Import an image, pick a model, then press Convert.", "none")
        go = tk.Frame(b); go.grid(row=11, column=0, sticky="ew", pady=(10, 0)); go.columnconfigure(0, weight=1, uniform="g"); go.columnconfigure(1, weight=1, uniform="g"); self.go = go
        self.btn_logisim = Btn(ctx, go, "Open in Logisim   ▶", lambda: self.open_result("digital"), "primary"); self.btn_logisim.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_multisim = Btn(ctx, go, "Open in Multisim   ▶", lambda: self.open_result("analog"), "primary"); self.btn_multisim.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.result_kind = None; self.set_result(None)
        self.provider_changed(first=True)
        if PROVIDERS[self.prov.get()].local: self.check_ollama()
        ctx.themed.append(self._paint); self._paint()
        ctx.root.after(150, self._poll)

    def _paint(self):
        P = self.ctx.P
        for w in (self.body, self.top, self.pm, self.act, self.go): w.configure(bg=P["card"])
        for w in self.muted: w.configure(bg=P["card"], fg=P["muted"])
        self.lbl_prev.configure(bg=P["field"], fg=P["muted"]); self.prev_box.configure(bg=P["field"], highlightbackground=P["border"])

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
    def provider_changed(self, first=False):
        p = PROVIDERS[self.prov.get()]; cfg = self.ctx.cfg
        self.cb_model.configure(values=p.models)
        self.model.set(cfg.get("models", {}).get(p.name) or p.models[0])
        self.key.set(os.environ.get(p.env, "") if p.env else "")
        for w in (self.key_lbl, self.key_ent): (w.grid() if p.env else w.grid_remove())
        self.base.set(cfg.get("bases", {}).get(p.name) or p.base)
        for w in (self.base_lbl, self.base_ent): (w.grid() if p.show_base else w.grid_remove())
        (self.btn_pull.grid() if p.local else self.btn_pull.grid_remove())
        if p.local and not first: self.check_ollama()
        self.help.config(text=p.help + ("  (key found in environment)" if p.env and os.environ.get(p.env) else "") + "  The image is sent to this service.")

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

    def _later_preview(self):
        if self.prev_job: self.ctx.root.after_cancel(self.prev_job)
        self.prev_job = self.ctx.root.after(120, self._render_preview)

    def _render_preview(self):
        self.prev_job = None; data, path = self.prev_data, getattr(self, "prev_path", None)
        if not data: return
        W, H = max(120, self.prev_box.winfo_width() - 12), max(80, self.prev_box.winfo_height() - 12)
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
            im.thumbnail((W, H)); out = io.BytesIO(); im.save(out, "PNG")
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
