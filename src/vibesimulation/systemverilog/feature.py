"""Feature (Template Method) and the registry that finds every feature file (Registry)."""


class Feature:
    """One SystemVerilog feature = one file. ``run`` decides whether it has work to do, ``apply`` does it."""
    name = ""
    summary = ""                 # one line for the documentation / the Output tab
    order = 100                  # features run from the lowest order to the highest
    stage = "tokens"             # "text" features see the raw text, "tokens" features see the token list
    triggers = ()                # words that must appear for the feature to run at all ((): always run)

    def run(self, ctx):
        if self.applies(ctx): self.apply(ctx)

    def applies(self, ctx):
        if not self.triggers: return True
        if self.stage == "text": return any(w in ctx.text for w in self.triggers)
        return any(t.text in self.triggers for t in ctx.tokens)

    def apply(self, ctx): raise NotImplementedError


class FeatureRegistry:
    def __init__(self): self._features = {}

    def register(self, feat):
        if feat.name in self._features: raise ValueError(f"two features are called {feat.name}")
        self._features[feat.name] = feat

    def ordered(self, stage=None):
        return sorted((f for f in self._features.values() if stage in (None, f.stage)), key=lambda f: (f.order, f.name))

    def get(self, name): return self._features[name]


REGISTRY = FeatureRegistry()


def feature(cls):
    """Class decorator: ``@feature`` makes the feature part of every lowering run."""
    REGISTRY.register(cls()); return cls
