"""Compiler directives: `define (with arguments), `undef, `ifdef / `ifndef / `elsif / `else / `endif, `include and `NAME uses, plus the -D / -I of the
simulation settings. The work is done by the Verilog preprocessor (verilog/preproc.py), so both sections read macros the same way. Lines keep their numbers."""
from vibesimulation.workspaces.verilog.core.preproc import preprocess
from vibesimulation.workspaces.systemverilog.core.feature import Feature, feature
@feature
class Preprocess(Feature):
    name = "preprocess"
    summary = "`define / `ifdef / `include macro expansion"
    order = 10
    stage = "text"
    triggers = ("`",)

    def apply(self, ctx):
        ctx.text = preprocess(ctx.text)
