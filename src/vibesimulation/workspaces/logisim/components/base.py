"""Draw context handed to Component.draw()."""


class DrawContext:
    """What a symbol needs while drawing: current pin values and the tags that make it clickable."""
    def __init__(self, values=None, body_tags=(), names=True):
        self.values = values or {}      # pin name -> current value (int, None = error, missing = unknown)
        self.body_tags = tuple(body_tags)
        self.names = names

    def val(self, pin, default=0):
        return self.values.get(pin, default)
