"""Setting: ai button."""
from vibesimulation.workspaces.settings.item import D
def item(page):
    return D("Appearance", "AI assistant button", "The round button at the bottom right that opens the AI prompt bar (Ctrl+J).", page.switch("ai_button", True))
