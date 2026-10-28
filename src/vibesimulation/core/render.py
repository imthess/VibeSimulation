"""Renderer interface (Bridge pattern).

Components describe how they look by calling these methods. The screen (Tk canvas) and the PDF
writer each implement Renderer, so a symbol is drawn once and appears the same everywhere.
Colour 'roles' (not hex codes) keep light/dark themes and printing independent of the shapes.
"""
from abc import ABC, abstractmethod

OUTLINE, FILL, MUTED, ON, OFF, LABEL, ACCENT, BAD = "outline", "fill", "muted", "on", "off", "label", "accent", "bad"


class Renderer(ABC):
    @abstractmethod
    def line(self, pts, width=2, role=OUTLINE, tags=()): ...

    @abstractmethod
    def polygon(self, pts, fill=FILL, outline=OUTLINE, width=2, tags=()): ...

    @abstractmethod
    def circle(self, cx, cy, r, fill=FILL, outline=OUTLINE, width=2, tags=()): ...

    @abstractmethod
    def rect(self, x0, y0, x1, y1, fill=FILL, outline=OUTLINE, width=2, tags=()): ...

    @abstractmethod
    def text(self, x, y, s, size=10, role=MUTED, bold=False, anchor="c", tags=()): ...
