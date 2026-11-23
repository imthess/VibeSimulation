"""Setting: short answer format instead of JSON (idea 5: about 40% fewer answer tokens)."""
from vibesimulation.workspaces.ai_import.core import tuning
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Short answer format", "Ask the AI to answer in a few short lines instead of JSON; the program converts them back. Saves answer tokens. If a model ignores it, JSON is still understood.",
             page.switch("ai_compact_answer", True, lambda: tuning.apply(page.ctx.cfg)))
