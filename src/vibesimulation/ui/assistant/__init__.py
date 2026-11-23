"""The AI assistant: a prompt bar (opened by the round button at the bottom right) that edits the circuit, its JSON or its code.

``controller.py`` is the window part, ``targets.py`` knows what to send and how to apply the answer for each workspace, ``session.py`` runs one
request (with automatic repair of answers that do not compile); ``fab.py``, ``bar.py`` and ``backdrop.py`` draw the button and the bar."""
