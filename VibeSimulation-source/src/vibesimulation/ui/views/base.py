"""Base class of the four boxes."""
from abc import ABC, abstractmethod


class View(ABC):
    """One box of the window. It reads the Document and redraws when the Document says it changed."""
    number = 0
    title = ""
    hint = ""

    def __init__(self, ctx, doc, parent):
        from ..widgets import Card
        self.ctx, self.doc = ctx, doc
        self.card = Card(ctx, parent, self.number, self.title, self.hint, flat=True)
        self.body, self.tools = self.card.body, self.card.tools
        self.build()
        doc.subscribe(self.on_doc)

    @abstractmethod
    def build(self):
        """Create the widgets inside ``self.body`` / ``self.tools``."""

    def on_doc(self, kind):
        """Called whenever the Document changes (kind: 'changed' or 'values')."""
