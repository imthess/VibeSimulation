"""Full-size picture window: opens when the preview is double-clicked; zoom with + / - / mouse wheel, drag to move."""
import base64
import io
import tkinter as tk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None


class PictureViewer(tk.Toplevel):
    def __init__(self, ctx, data, title="Picture"):
        super().__init__(ctx.root); self.title(title); self.geometry("1000x700"); self.ctx = ctx
        self.c = tk.Canvas(self, bd=0, highlightthickness=0, bg="#2a2a2e"); self.c.pack(fill="both", expand=True)
        self.im = Image.open(io.BytesIO(data)) if Image is not None else None
        if self.im is not None: self.im.load()
        self.zoom, self.fit_done, self.tk_img = 1.0, False, None
        self.bind("<plus>", lambda e: self.set_zoom(self.zoom * 1.25)); self.bind("<equal>", lambda e: self.set_zoom(self.zoom * 1.25))
        self.bind("<minus>", lambda e: self.set_zoom(self.zoom / 1.25)); self.bind("<Key-0>", lambda e: self.fit()); self.bind("<Escape>", lambda e: self.destroy())
        self.c.bind("<MouseWheel>", lambda e: self.set_zoom(self.zoom * (1.15 if e.delta > 0 else 1 / 1.15)))
        self.c.bind("<Button-4>", lambda e: self.set_zoom(self.zoom * 1.15)); self.c.bind("<Button-5>", lambda e: self.set_zoom(self.zoom / 1.15))
        self.c.bind("<ButtonPress-1>", lambda e: self.c.scan_mark(e.x, e.y)); self.c.bind("<B1-Motion>", lambda e: self.c.scan_dragto(e.x, e.y, gain=1))
        self.c.bind("<Configure>", lambda e: None if self.fit_done else self.fit())
        self.hint = self.c.create_text(10, 8, anchor="nw", fill="#cfcfd6", text="+ / - or wheel: zoom    0: fit    drag: move    Esc: close", font=ctx.f_small)
        self.focus_set()

    def fit(self):
        if self.im is None: return
        W, H = max(50, self.c.winfo_width()), max(50, self.c.winfo_height())
        self.fit_done = True; self.set_zoom(min(W / self.im.width, H / self.im.height, 4.0), center=True)

    def set_zoom(self, z, center=False):
        if self.im is None: return
        self.zoom = max(0.05, min(z, 8.0))
        w, h = max(1, int(self.im.width * self.zoom)), max(1, int(self.im.height * self.zoom))
        im = self.im.convert("RGBA").resize((w, h), Image.LANCZOS if self.zoom < 1 else Image.BICUBIC)
        self.tk_img = ImageTk.PhotoImage(im) if ImageTk is not None else None
        if self.tk_img is None: return
        self.c.delete("img"); W, H = self.c.winfo_width(), self.c.winfo_height()
        x, y = (max(0, (W - w) // 2), max(0, (H - h) // 2)) if center or w < W else (0, 0)
        self.c.create_image(x, y, image=self.tk_img, anchor="nw", tags="img"); self.c.tag_lower("img")
        self.c.configure(scrollregion=(0, 0, max(W, w + 2 * x), max(H, h + 2 * y)))
