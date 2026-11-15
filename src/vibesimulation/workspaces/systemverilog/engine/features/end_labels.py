"""`end : name`, `endmodule : name`, `endfunction : name` ... : the label after the closing keyword is dropped."""
from ..feature import Feature, feature

CLOSERS = {"end", "endmodule", "endfunction", "endtask", "endcase", "endgenerate", "endpackage", "join", "endinterface"}


@feature
class EndLabels(Feature):
    name = "end_labels"
    summary = "labels after end / endmodule / endfunction ..."
    order = 30
    triggers = tuple(CLOSERS)

    def apply(self, ctx):
        ed = ctx.editor(); toks = ctx.tokens
        for i, t in enumerate(toks[:-2]):
            if t.kind == "id" and t.text in CLOSERS and toks[i + 1].text == ":" and toks[i + 1].kind == "op" and toks[i + 2].kind == "id": ed.delete(i + 1, i + 3)
        ctx.commit(ed)
