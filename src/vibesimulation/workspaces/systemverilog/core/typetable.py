"""The user-defined types of a run (typedef, enum, packed struct): shared by the features that define or use them."""
from dataclasses import dataclass, field


@dataclass
class TypeInfo:
    name: str
    head: str                          # what a declaration of this type is written as in the lowered text, e.g. "logic [3:0]"
    width: int = None
    kind: str = "alias"                # alias | enum | struct
    fields: dict = field(default_factory=dict)       # struct: field name -> (high bit, low bit)
    values: dict = field(default_factory=dict)       # enum: member name -> value


class TypeTable:
    def __init__(self): self._t = {}

    def define(self, info): self._t[info.name] = info

    def get(self, name): return self._t.get(name)

    def __contains__(self, name): return name in self._t

    def names(self): return list(self._t)

    def of_kind(self, kind): return [t for t in self._t.values() if t.kind == kind]
