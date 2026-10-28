"""The last feature (Verifier): anything that is still SystemVerilog here was not understood, and is reported with its line."""
from ..feature import Feature, feature

WORDS = {"logic", "bit", "byte", "shortint", "longint", "int", "enum", "struct", "union", "typedef", "always_comb", "always_ff", "always_latch", "inside", "return", "assert",
         "package", "endpackage", "import", "unique", "unique0", "priority", "void", "interface", "endinterface", "class", "final", "break", "continue", "foreach", "do"}
OPS = {"++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>=", "::", "'{", ".*", "'", "==?", "!=?", "<->", "|->", "|=>", "##"}


@feature
class Leftover(Feature):
    name = "leftover"
    summary = "refuses SystemVerilog that no feature could lower"
    order = 990

    def apply(self, ctx):
        for t in ctx.tokens:
            if t.kind == "id" and t.text in WORDS: ctx.fail(t.line, f"SystemVerilog: '{t.text}' is not supported in this place")
            if t.kind == "op" and t.text in OPS: ctx.fail(t.line, f"SystemVerilog: '{t.text}' is not supported in this place (as a statement it is; inside an expression use the long form)")
            if t.kind == "fill": ctx.fail(t.line, f"SystemVerilog: {t.text} is not supported in this place")
