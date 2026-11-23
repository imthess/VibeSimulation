"""Setting: how OpenRouter chooses the model (idea 3)."""
from vibesimulation.workspaces.ai_import.core import tuning
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "OpenRouter model choice", "Best picture model: the newest free model that can see pictures (predictable). Free router: OpenRouter picks any free model each time (may be slow or think a lot).",
             page.seg("ai_openrouter_pick", [("Best picture model", "best"), ("Free router", "router")], "best", after=lambda: tuning.apply(page.ctx.cfg)))
