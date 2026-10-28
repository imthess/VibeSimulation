"""Component registry (Registry + Factory patterns).

Every component class registers itself with ``@register``. The rest of the program asks the
registry to build a component from its JSON name, so adding a new component never requires
touching the parser, the layout or the user interface.
"""


def _key(name):
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


class ComponentRegistry:
    _classes = {}

    @classmethod
    def register(cls, comp_cls):
        cls._classes[_key(comp_cls.type_name)] = comp_cls
        for alias in getattr(comp_cls, "aliases", ()):
            cls._classes.setdefault(_key(alias), comp_cls)
        return comp_cls

    @classmethod
    def lookup(cls, type_name):
        return cls._classes.get(_key(type_name))

    @classmethod
    def known(cls):
        return sorted({c.type_name for c in cls._classes.values()})

    @classmethod
    def by_category(cls):
        groups = {}
        for c in {id(c): c for c in cls._classes.values()}.values():
            groups.setdefault(c.category, []).append(c)
        return groups

    @classmethod
    def create(cls, type_name, cid, attrs=None, ins=None, outs=None):
        c = cls.lookup(type_name)
        if c is None:
            raise ValueError(f"unknown component type '{type_name}'")
        return c(cid, attrs, ins, outs)

    @classmethod
    def from_dict(cls, d):
        """Build a component from one JSON object of the "gates" list."""
        c = cls.lookup(d.get("type", ""))
        if c is None:
            raise ValueError(f"unknown type '{d.get('type')}'. Known types: {', '.join(sorted(cls.known()))}")
        settings = {a.name: d[a.name] for a in c.attrs_spec if a.name in d}
        obj = c(str(d.get("id") or ""), settings)
        obj.load_dict(d)
        return obj


register = ComponentRegistry.register
