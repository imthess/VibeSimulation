"""Tiny Observer helper: objects call ``subscribe(fn)``; the subject calls ``notify(kind)``."""


class Subject:
    def __init__(self):
        self._listeners = []

    def subscribe(self, fn):
        self._listeners.append(fn)
        return fn

    def unsubscribe(self, fn):
        if fn in self._listeners: self._listeners.remove(fn)

    def notify(self, kind="changed"):
        for fn in list(self._listeners):
            fn(kind)
