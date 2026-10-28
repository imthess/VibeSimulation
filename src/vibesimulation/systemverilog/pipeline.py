"""The lowering pipeline: text features, then the lexer, then token features, in order (Pipeline / Chain of Responsibility)."""
from . import features as _features          # noqa: F401  (importing the package registers every feature)
from .context import Context
from .feature import REGISTRY
from .lexer import emit, lex


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
