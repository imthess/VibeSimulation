"""Choose the part of the picture that is sent: drag the frame (or its corners and edges); Auto finds the circuit by itself."""
import base64
import io
import tkinter as tk

from vibesimulation.ui.controls.widgets import Btn
from vibesimulation.workspaces.ai_import.core import scan

GRAB = 10          # px around a corner / edge that grabs it


class CropDialog(tk.Toplevel):
    """``result``: a box (x0, y0, x1, y1) in the picture's own pixels, the string "auto", or None when cancelled."""
    def __init__(self, ctx, data, box, opts):
        super().__init__(ctx.root); P = ctx.P; self.result = None; self.opts = opts
        self.title("Crop the picture"); self.configure(bg=P["card"]); self.transient(ctx.root)
        self.im = scan.open_image(data); W, H = self.im.size
        sw, sh = ctx.root.winfo_screenwidth(), ctx.root.winfo_screenheight()
        self.k = min((min(900, sw - 120)) / W, (min(600, sh - 260)) / H, 1.0)             # picture pixels -> screen pixels
        w, h = max(1, round(W * self.k)), max(1, round(H * self.k))
        small = self.im.resize((w, h)); out = io.BytesIO(); small.save(out, "PNG"); self.photo = tk.PhotoImage(data=base64.b64encode(out.getvalue()))
        tk.Label(self, text="Drag the frame so it holds only the circuit. Drag inside to move it, drag a corner or edge to resize it.", bg=P["card"], fg=P["muted"], font=ctx.f_small, anchor="w").pack(fill="x", padx=16, pady=(14, 6))
        self.c = tk.Canvas(self, width=w, height=h, bd=0, highlightthickness=0, bg=P["card"]); self.c.pack(padx=16)
        self.c.create_image(0, 0, image=self.photo, anchor="nw")
        self.box = list(box if box else scan.auto_box(self.im, opts)); self.box = list(scan.clean_box(self.box, self.im.size))
        self.drag = None; self.note = tk.Label(self, text="", bg=P["card"], fg=P["muted"], font=ctx.f_small, anchor="w"); self.note.pack(fill="x", padx=16, pady=(6, 0))
        self.c.bind("<ButtonPress-1>", self.press); self.c.bind("<B1-Motion>", self.move); self.c.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None)); self.c.bind("<Motion>", self.hover)
        row = tk.Frame(self, bg=P["card"]); row.pack(fill="x", padx=16, pady=14)
        Btn(ctx, row, "Use this crop", self.ok, "primary").pack(side="right", padx=(8, 0)); Btn(ctx, row, "Cancel", self.destroy, "secondary").pack(side="right")
        Btn(ctx, row, "Automatic", self.auto, "ghost").pack(side="left"); Btn(ctx, row, "Whole picture", self.whole, "ghost").pack(side="left", padx=8)
        self.bind("<Escape>", lambda e: self.destroy()); self.draw()
        self.update_idletasks(); r = ctx.root
        self.geometry(f"+{max(0, r.winfo_rootx() + (r.winfo_width() - self.winfo_width()) // 2)}+{max(0, r.winfo_rooty() + (r.winfo_height() - self.winfo_height()) // 3)}")
        try: self.grab_set()
        except tk.TclError: pass

    # ---- geometry
    def screen(self): return [v * self.k for v in self.box]

    def draw(self):
        c = self.c; c.delete("fr"); x0, y0, x1, y1 = self.screen(); W, H = int(c["width"]), int(c["height"])
        for r in ((0, 0, W, y0), (0, y1, W, H), (0, y0, x0, y1), (x1, y0, W, y1)):
            c.create_rectangle(*r, fill="#000000", stipple="gray50", outline="", tags="fr")                # dim everything outside the frame
        c.create_rectangle(x0, y0, x1, y1, outline="#ffffff", width=3, tags="fr"); c.create_rectangle(x0, y0, x1, y1, outline="#2d6cdf", width=1, tags="fr")
        for x in (x0, x1):
            for y in (y0, y1): c.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill="#2d6cdf", outline="#ffffff", tags="fr")
        bx = scan.clean_box(self.box, self.im.size)
        self.note.config(text=f"Crop: {bx[2] - bx[0]} × {bx[3] - bx[1]} px of {self.im.width} × {self.im.height}")

    def where(self, x, y):
        """Which part of the frame the pointer is on: letters l r t b for edges (two = corner), 'm' inside, '' outside."""
        x0, y0, x1, y1 = self.screen(); hit = ""
        if y0 - GRAB <= y <= y1 + GRAB:
            if abs(x - x0) <= GRAB: hit += "l"
            elif abs(x - x1) <= GRAB: hit += "r"
        if x0 - GRAB <= x <= x1 + GRAB:
            if abs(y - y0) <= GRAB: hit += "t"
            elif abs(y - y1) <= GRAB: hit += "b"
        return hit or ("m" if x0 < x < x1 and y0 < y < y1 else "")

    CURSORS = {"l": "sb_h_double_arrow", "r": "sb_h_double_arrow", "t": "sb_v_double_arrow", "b": "sb_v_double_arrow", "lt": "top_left_corner", "rb": "bottom_right_corner",
               "rt": "top_right_corner", "lb": "bottom_left_corner", "m": "fleur", "": "arrow"}

    def hover(self, e): self.c.configure(cursor=self.CURSORS.get(self.where(e.x, e.y), "arrow"))

    def press(self, e):
        part = self.where(e.x, e.y)
        if not part:                                                                  # a click outside starts a new frame
            self.box = [e.x / self.k, e.y / self.k, e.x / self.k + 20, e.y / self.k + 20]; part = "rb"
        self.drag = (part, e.x, e.y, list(self.box))

    def move(self, e):
        if not self.drag: return
        part, x, y, b0 = self.drag; dx, dy = (e.x - x) / self.k, (e.y - y) / self.k; W, H = self.im.size; b = list(b0)
        if part == "m":
            w, h = b[2] - b[0], b[3] - b[1]; b[0] = max(0, min(W - w, b[0] + dx)); b[1] = max(0, min(H - h, b[1] + dy)); b[2], b[3] = b[0] + w, b[1] + h
        else:
            if "l" in part: b[0] = max(0, min(b[2] - 20, b[0] + dx))
            if "r" in part: b[2] = min(W, max(b[0] + 20, b[2] + dx))
            if "t" in part: b[1] = max(0, min(b[3] - 20, b[1] + dy))
            if "b" in part: b[3] = min(H, max(b[1] + 20, b[3] + dy))
        self.box = b; self.draw()

    # ---- buttons
    def auto(self): self.box = list(scan.auto_box(self.im, self.opts)); self.draw()

    def whole(self): self.box = [0, 0, self.im.width, self.im.height]; self.draw()

    def ok(self): self.result = scan.clean_box(self.box, self.im.size); self.destroy()
