"""Contents editor for ROM (like Logisim's hex editor): rows of 8 hex values, 'ADDR: v0 v1 ... v7'."""
import tkinter as tk
from tkinter import filedialog

from ..widgets import Btn
from .parts_palette import _Modal


def to_text(contents, addr_bits, width, per_row=8):
    digits = max(1, (width + 3) // 4); adigits = max(2, (addr_bits + 3) // 4); n = 1 << addr_bits
    last = max(contents, default=-1)
    rows = max(1, min(n, last + 1 + per_row) // per_row + (0 if min(n, last + 1 + per_row) % per_row == 0 else 1))
    out = []
    for r in range(rows):
        base = r * per_row
        if base >= n: break
        out.append(f"{base:0{adigits}X}: " + " ".join(f"{contents.get(base + k, 0):0{digits}X}" for k in range(per_row) if base + k < n))
    return "\n".join(out)


def from_text(text, addr_bits, width):
    """'ADDR: v v v' lines (hex; '#' starts a comment; a line without 'ADDR:' continues after the previous one) -> {address: value}."""
    out, nxt, n = {}, 0, 1 << addr_bits
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln: continue
        if ":" in ln:
            a, _, ln = ln.partition(":"); nxt = int(a.strip(), 16)
        for tok in ln.split():
            if "*" in tok: k, v = tok.split("*", 1); k, v = int(k), int(v, 16)
            else: k, v = 1, int(tok, 16)
            for _ in range(k):
                if nxt >= n: raise ValueError(f"address {nxt:X} does not fit in {addr_bits} address bits")
                if v >> width: raise ValueError(f"value {v:X} at address {nxt:X} does not fit in {width} bits")
                if v: out[nxt] = v
                nxt += 1
    return out


class MemoryEditor(_Modal):
    """result = {address: value} or None."""
    def __init__(self, ctx, title, contents, addr_bits, width):
        super().__init__(ctx, title)
        P = ctx.P; self.ab, self.w = addr_bits, width
        tk.Label(self, text=title, bg=P["card"], fg=P["text"], font=ctx.f_title).pack(anchor="w", padx=20, pady=(16, 2))
        tk.Label(self, text=f"{1 << addr_bits} addresses x {width} bits. Hex values; each line starts with its address. Values you leave out are 0. 'n*v' repeats a value n times.",
                 bg=P["card"], fg=P["muted"], font=ctx.f_small, wraplength=520, justify="left").pack(anchor="w", padx=20)
        f = tk.Frame(self, bg=P["card"]); f.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt = tk.Text(f, width=62, height=18, font=ctx.f_mono, bd=0, highlightthickness=1, highlightbackground=P["line"] if "line" in P else P["soft"], bg=P["field"], fg=P["text"], insertbackground=P["text"], padx=8, pady=6)
        sb = tk.Scrollbar(f, command=self.txt.yview); self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.txt.insert("1.0", to_text(contents, addr_bits, width))
        self.err = tk.Label(self, text="", bg=P["card"], fg=P["bad"], font=ctx.f_small, wraplength=520, justify="left"); self.err.pack(anchor="w", padx=20)
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=20, pady=14)
        Btn(ctx, row, "OK", self.ok, "primary").pack(side="right", padx=(8, 0)); Btn(ctx, row, "Cancel", self.destroy, "secondary").pack(side="right")
        Btn(ctx, row, "Open .hex / .txt…", self.load, "ghost").pack(side="left"); Btn(ctx, row, "Clear", lambda: self.txt.delete("1.0", "end"), "ghost").pack(side="left", padx=(6, 0))
        self.show()

    def load(self):
        p = filedialog.askopenfilename(parent=self, title="Open memory image", filetypes=[("Memory image", "*.hex *.txt *.mem *.*")])
        if not p: return
        try:
            with open(p, encoding="utf-8", errors="replace") as fh: text = fh.read()
            if text.startswith("v2.0 raw"): text = text.split("\n", 1)[1]          # Logisim's own memory file format
            c = from_text(text if ":" in text else "0: " + text, self.ab, self.w)
        except Exception as e:
            self.err.config(text=f"Could not read the file: {e}"); return
        self.txt.delete("1.0", "end"); self.txt.insert("1.0", to_text(c, self.ab, self.w)); self.err.config(text="")

    def ok(self):
        try: self.result = from_text(self.txt.get("1.0", "end"), self.ab, self.w)
        except ValueError as e: self.err.config(text=f"Not accepted: {e}"); return
        self.destroy()
