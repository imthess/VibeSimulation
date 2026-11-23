"""The lowering pipeline: text features, then the lexer, then token features, in order (Pipeline / Chain of Responsibility)."""
import vibesimulation.workspaces.systemverilog.core.features as _features
from vibesimulation.workspaces.systemverilog.core.context import Context
from vibesimulation.workspaces.systemverilog.core.feature import REGISTRY
from vibesimulation.workspaces.systemverilog.core.lexer import emit, lex
class Pipeline:
    def __init__(self, registry=REGISTRY): self.registry = registry

    def run(self, text, only=None, known=None):
        """-> Context whose ``tokens`` are the lowered program. Raises VError (with the line) for the first problem.
        `only`: names of the features to run (used by tests of one feature)."""
        ctx = Context(text, known)
        pick = lambda f: only is None or f.name in only
        for f in self.registry.ordered("text"):
            if pick(f): f.run(ctx)
        ctx.tokens = lex(ctx.text)
        for f in self.registry.ordered("tokens"):
            if pick(f): f.run(ctx)
        return ctx

    @staticmethod
    def text_of(ctx): return emit(ctx.tokens)
