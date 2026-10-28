"""always_comb / always_latch become `always @*`; always_ff becomes `always` (its event control follows)."""
from ..analysis import assignments_in
from ..feature import Feature, feature
from ..scan import stmt_end
from ..lexer import Tok


@feature
class AlwaysBlocks(Feature):
    name = "always_blocks"
    summary = "always_comb, always_latch, always_ff"
    order = 20
    triggers = ("always_comb", "always_ff", "always_latch")

    def apply(self, ctx):
        ed = ctx.editor()
        for i, t in enumerate(ctx.tokens):
            if t.kind != "id": continue
            if t.text in ("always_comb", "always_latch"):
                for name, start, op in assignments_in(ctx.tokens, i + 1, stmt_end(ctx.tokens, i + 1)):          # `<=` is legal in SystemVerilog's combinational blocks
                    if ctx.tokens[op].text == "<=": ed.replace(op, op + 1, [Tok("op", "=", ctx.tokens[op].line)])
                ed.replace(i, i + 1, [Tok("id", "always", t.line), Tok("op", "@", t.line), Tok("op", "*", t.line)])
            elif t.text == "always_ff":
                if ctx.tokens[i + 1].text != "@": ctx.fail(t.line, "always_ff needs an event control such as @(posedge clk)")
                ed.replace(i, i + 1, [Tok("id", "always", t.line)])
        ctx.commit(ed)
