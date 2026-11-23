"""Setting: limit the AI's hidden thinking (idea 2: it is billed as output tokens, and is the biggest cost of one picture)."""
from vibesimulation.workspaces.ai_import.core import tuning
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("AI & Import", "Limit the AI's hidden thinking", "Many models \"think\" before they answer and bill that as output. On: they are told to think little (Gemini, OpenRouter, OpenAI o-series). Turn off if answers get worse.",
             page.switch("ai_limit_reasoning", True, lambda: tuning.apply(page.ctx.cfg)))
