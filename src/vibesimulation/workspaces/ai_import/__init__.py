"""The Import & AI tab: turn a picture into a circuit, or open a circuit file.

- ``core/``      talking to the AI providers (``providers.py``), the prompts per target (``prompt.py``), key detection and storage
- ``imports/``   ``load_file`` / ``classify``: opens any circuit file (.circ, SPICE, our JSON) and says whether it is digital or analog
- ``ui/``        the page (``import_view.py``) and its look"""
