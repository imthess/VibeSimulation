"""The only code shared by several tabs (everything else belongs to one tab, see ``workspaces/``):

- ``render.py``    ``Renderer``: the drawing interface (screen, PDF and PNG all implement it) and its colour roles
- ``events.py``    ``Subject``: tiny observer used by the documents
- ``routing.py``, ``wire_edit.py``   wire routing and wire editing geometry used by the Logisim and Multisim drawings
- ``pdf_writer.py``, ``png_writer.py``   the PDF and PNG writers; each tab's ``export/`` builds its own report on top of them"""
