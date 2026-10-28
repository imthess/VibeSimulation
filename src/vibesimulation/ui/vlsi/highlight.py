"""Verilog syntax colours for a Tk Text widget (comments, keywords, numbers, strings, library cells)."""
import re

KEYWORDS = frozenset(("module endmodule input output inout wire reg integer signed assign always initial begin end if else case casez casex endcase "
                      "default posedge negedge or and nand nor xor xnor not buf parameter localparam supply0 supply1 tri "
                      "function endfunction task endtask for while repeat forever generate endgenerate genvar time wait disable automatic").split())

_TOKEN = re.compile(r"//[^\n]*|/\*.*?\*/|\"[^\"\n]*\"|\b\d*'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_?]+|\b\d+\b|\$\w+|\bvs_\w+|\b[A-Za-z_]\w*\b", re.S)
TAGS = ("v_kw", "v_cm", "v_num", "v_str")


class VerilogHighlighter:
    WORDS = KEYWORDS                       # the SystemVerilog highlighter adds its own words

    def __init__(self, text_widget): self.t = text_widget

    def configure(self, P):
        """Colours come from the current theme palette P."""
        t = self.t
        t.tag_configure("v_kw", foreground=P["accent"]); t.tag_configure("v_cm", foreground=P["muted"])
        t.tag_configure("v_num", foreground=P["ok"]); t.tag_configure("v_str", foreground=P["ok"])

    def apply(self):
        t = self.t
        for tag in TAGS: t.tag_remove(tag, "1.0", "end")
        text = t.get("1.0", "end")
        for m in _TOKEN.finditer(text):
            g = m.group(0); tag = None
            if g.startswith("//") or g.startswith("/*"): tag = "v_cm"
            elif g.startswith('"'): tag = "v_str"
            elif g[0].isdigit() or g[0] == "'": tag = "v_num"
            elif g.startswith("vs_") or g.startswith("$") or g in self.WORDS: tag = "v_kw"
            if tag: t.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for tag in TAGS: t.tag_lower(tag)
