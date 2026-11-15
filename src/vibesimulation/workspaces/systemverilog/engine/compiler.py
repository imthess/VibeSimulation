"""Facade: SystemVerilog text in, lowered Verilog text (and warnings) out."""
from dataclasses import dataclass, field

from .pipeline import Pipeline


@dataclass
class Lowered:
    verilog: str
    warnings: list = field(default_factory=list)       # [(line, message)]
    changed: bool = True


def lower(text, known=None):
    """Raises ``VError`` (with a line number) for what cannot be lowered.
    `known`: {module name: [port names]} of modules defined elsewhere (the other circuits of the project), for `.*` connections."""
    ctx = Pipeline().run(text, known=known)
    return Lowered(Pipeline.text_of(ctx), list(ctx.warnings))
