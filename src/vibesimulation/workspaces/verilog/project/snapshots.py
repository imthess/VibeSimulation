"""Remembers the Verilog the user typed for each circuit (Memento pattern).

A snapshot is valid only while the circuit is still *exactly* what that text produced. The check compares the circuit's
canonical JSON (positions and wire routes are not part of it), so moving parts around never throws the user's text away,
while any change of logic makes the Verilog be written again from the circuit.
"""


class SnapshotStore:
    def __init__(self):
        self._items = {}          # circuit name -> (verilog text, canonical json text it produced)

    def put(self, name, text, canon): self._items[name] = (text, canon)

    def get(self, name): return self._items.get(name)

    def valid_text(self, name, canon):
        """The typed text of `name` if the circuit (given as canonical JSON) is still what it produced, else None."""
        snap = self._items.get(name)
        if snap and (canon is None or snap[1] == canon): return snap[0]
        return None

    def last_text(self, name):
        snap = self._items.get(name); return snap[0] if snap else ""

    def rename(self, old, new):
        self._items = {(new if n == old else n): v for n, v in self._items.items()}

    def drop(self, name): self._items.pop(name, None)

    def clear(self): self._items = {}
