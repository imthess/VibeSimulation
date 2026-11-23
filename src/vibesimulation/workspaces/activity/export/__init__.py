"""Download the activity report: ``save_markdown`` and ``save_pdf`` take the report text and a path."""
from pathlib import Path

from vibesimulation.workspaces.activity.export import pdf


def save_markdown(text, path): Path(path).write_text(text, encoding="utf-8")


def save_pdf(text, path): Path(path).write_bytes(pdf.build(text))
