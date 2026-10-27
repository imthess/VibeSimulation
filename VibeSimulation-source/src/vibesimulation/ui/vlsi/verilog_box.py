"""VLSI pane 1: the Verilog editor.

Typing compiles the text after a short pause (``VlsiDocument.set_verilog``). A mistake changes nothing: the circuit stays as it
was, the faulty lines turn red and the typed text is kept until it compiles. When the circuit changes some other way (an
undo, a different circuit, a file opened) the editor shows the Verilog of the new state.
"""
from ..views.code_view import CodeView
from ..widgets import Segmented
from .highlight import VerilogHighlighter


class VerilogView(CodeView):
    number, title, hint = None, "Verilog", "the circuit follows what you type"
    NAME = "Verilog"
    DELAY = 450                 # a compile is heavier than a JSON parse: wait a little longer

    page = None

    def build(self):
        self._dirty, self._dirty_ver, self._shown, self._hl_job = False, -1, None, None
        self.mode = "design"                                   # "design" | "tb" (the Testbench tab)
        super().build()
        self.hl = VerilogHighlighter(self.txt); self.hl.configure(self.ctx.P)
        self.which = Segmented(self.ctx, self.tools, [("Design", "design"), ("Test", "tb")], "design", self.switch)
        self.which.pack(side="right", padx=(0, 8), before=self.b_undo)
        self.txt.bind("<ButtonRelease-1>", lambda e: self._cursor_moved(), add="+"); self.txt.bind("<KeyRelease>", lambda e: self._cursor_moved(), add="+")
        self._last_line = None

    # ---- Design | Testbench
    def switch(self, mode):
        if mode == self.mode: return
        self.flush()
        self.mode = mode; self.which.set(mode); self.mark_lines(set())
        self._load()

    def _load(self):
        if self.mode == "tb":
            self.show_text(self.doc.tb_text.rstrip("\n"))
            self.status.set("Testbench: write a module with `initial` / `always`, #delays, $display, $finish. Press ▶ Run below.", "info")
        else:
            self.show_text(self.doc.verilog()); self._shown = None; self._report("✔ ")
        self.hl.apply()

    def goto(self, line, tb=False, focus=True):
        """Put the cursor on `line` of the design (or testbench) text."""
        want = "tb" if tb else "design"
        if want != self.mode: self.switch(want)
        n = int(self.txt.index("end-1c").split(".")[0]); line = max(1, min(line or 1, n))
        self.txt.mark_set("insert", f"{line}.0"); self.txt.see(f"{line}.0")
        self.txt.tag_remove("jump", "1.0", "end"); self.txt.tag_add("jump", f"{line}.0", f"{line}.0 lineend+1c")
        self.ctx.root.after(1400, lambda: self.txt.tag_remove("jump", "1.0", "end"))
        if focus: self.txt.focus_set()
        self._gutter()

    def _cursor_moved(self):
        if self.mode != "design" or self.page is None: return
        ln = int(self.txt.index("insert").split(".")[0])
        if ln != self._last_line: self._last_line = ln; self.page.line_picked(ln)

    def paint_extra(self):
        if hasattr(self, "hl"): self.hl.configure(self.ctx.P)
        self.txt.tag_configure("jump", background=self.ctx.P["sel"])

    # ---- typing -> compile
    def on_typed(self):
        if self._hl_job: self.ctx.root.after_cancel(self._hl_job)
        self._hl_job = self.ctx.root.after(60, self._highlight)

    def _highlight(self):
        self._hl_job = None; self.hl.apply()

    def flush_text(self, text):
        d = self.doc; text = text + "\n"
        if self.mode == "tb":
            if text.strip() != d.tb_text.strip(): d.set_testbench(text if text.strip() else "")
            return
        if text == self._shown: return
        if not text.strip():
            d.set_text(""); self._dirty = False; return
        errs = d.set_verilog(text)
        if errs:
            self._dirty, self._dirty_ver = True, d.version
            self.mark_lines({ln for ln, _ in errs})
            self.status.set("\n".join(f"✘ line {ln}: {m}" for ln, m in errs[:8]), "bad")
        else:
            self._dirty = False; self._shown = text; self.mark_lines(set())
            self._report(f"✔ Compiled: ")

    def _report(self, lead):
        d = self.doc
        if d.valid:
            c = d.circuit; self.status.set(f"{lead}{len(c.inputs)} inputs, {len(c.components)} components, {len(c.outputs)} outputs", "ok")
        elif d.layout_error: self.status.set("✘ The circuit is valid but cannot be drawn cleanly: " + d.layout_error, "bad")
        else: self.status.set("✘ " + "\n✘ ".join(d.errors), "bad")

    # ---- document -> screen
    def on_doc(self, kind):
        if kind == "testbench" and self.mode == "tb":
            if self.get_text().strip() != self.doc.tb_text.strip(): self.show_text(self.doc.tb_text.rstrip("\n")); self.hl.apply()
            return
        if kind == "testbench" and self.mode == "design": return
        if kind != "changed": return
        if self.mode == "tb":
            self.b_undo.set_enabled(self.doc.can_undo()); self.b_redo.set_enabled(self.doc.can_redo()); return
        d = self.doc
        if self._dirty and d.version == self._dirty_ver: return          # the user's faulty text stays until it compiles
        want = d.verilog()
        if self.get_text() != want.rstrip("\n"): self.show_text(want)
        self._shown = want if want.endswith("\n") else want + "\n"; self._dirty = False; self.mark_lines(set())
        self._report("✔ Verilog and circuit agree: ")
        self.hl.apply(); self.b_undo.set_enabled(d.can_undo()); self.b_redo.set_enabled(d.can_redo())
