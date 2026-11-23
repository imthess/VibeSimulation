"""Drag a part from an explorer list onto a drawing: press on the item, move the mouse over the canvas, release where the part should go.

Clicking still works as before (Logisim: pick the part, then click the canvas; Multisim: double-click). This only adds the drag, which is what most
people try first. While dragging, a small label follows the mouse; over the canvas the view may show its own ghost (`hover`), and releasing anywhere
else cancels. Esc during the drag cancels too."""
import tkinter as tk

THRESHOLD = 6          # pixels the mouse must move before a press becomes a drag


class PaletteDrag:
    def __init__(self, ctx, tree, can_drag, canvas, drop, hover=None):
        """can_drag(iid) -> label text or None; canvas() -> the canvas that accepts drops (None = none right now);
        drop(iid, x, y) with x, y in that canvas's own pixels; hover(x, y) or hover(None, None) while dragging."""
        self.ctx, self.tree, self.can_drag, self.canvas, self.drop, self.hover = ctx, tree, can_drag, canvas, drop, hover
        self.iid = self.start = self.ghost = None; self.active = False
        tree.bind("<ButtonPress-1>", self._press, add="+"); tree.bind("<B1-Motion>", self._move, add="+"); tree.bind("<ButtonRelease-1>", self._release, add="+")
        tree.bind("<Escape>", lambda e: self._end(cancel=True), add="+")

    def _press(self, e):
        self.iid = self.tree.identify_row(e.y) or None; self.start = (e.x_root, e.y_root); self.active = False

    def _move(self, e):
        if not self.iid: return
        if not self.active:
            if abs(e.x_root - self.start[0]) + abs(e.y_root - self.start[1]) < THRESHOLD: return
            label = self.can_drag(self.iid)
            if not label: self.iid = None; return
            self.active = True; self._make_ghost(label); self.tree.configure(cursor="hand2")
        self.ghost.geometry(f"+{e.x_root + 14}+{e.y_root + 10}")
        c = self._over(e)
        if self.hover:
            if c is None: self.hover(None, None)
            else: self.hover(e.x_root - c.winfo_rootx(), e.y_root - c.winfo_rooty())

    def _release(self, e):
        if not self.active: self.iid = None; return
        c = self._over(e); iid = self.iid; x = y = 0
        if c is not None: x, y = e.x_root - c.winfo_rootx(), e.y_root - c.winfo_rooty()
        self._end()
        if c is not None: self.drop(iid, x, y)

    def _over(self, e):
        """The drop canvas when the pointer is above it, else None."""
        c = self.canvas()
        if c is None or not c.winfo_ismapped(): return None
        w = self.tree.winfo_containing(e.x_root, e.y_root)
        return c if w is c else None

    def _make_ghost(self, label):
        P = self.ctx.P; g = tk.Toplevel(self.tree); g.overrideredirect(True); g.attributes("-topmost", True)
        tk.Label(g, text=label.strip(), font=self.ctx.f_small, bg=P["accent"], fg=P["accent_fg"], padx=10, pady=4).pack(); self.ghost = g

    def _end(self, cancel=False):
        if self.ghost is not None: self.ghost.destroy(); self.ghost = None
        try: self.tree.configure(cursor="")
        except tk.TclError: pass
        if self.hover: self.hover(None, None)
        self.active = False; self.iid = None
