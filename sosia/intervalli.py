"""Insieme di intervalli [a, b) senza sovrapposizioni, con verifica in tempo logaritmico (0.5.0: PDF lunghi)."""
from __future__ import annotations

from bisect import bisect_right


class Intervalli:
    __slots__ = ("inizi", "fini")

    def __init__(self):
        self.inizi: list[int] = []
        self.fini: list[int] = []

    def libero(self, a: int, b: int) -> bool:
        i = bisect_right(self.inizi, a)
        if i > 0 and self.fini[i - 1] > a and self.inizi[i - 1] < b:
            return False
        # intervalli che cominciano dopo a: il primo decide (sono ordinati e disgiunti)
        return not (i < len(self.inizi) and self.inizi[i] < b)

    def aggiungi(self, a: int, b: int) -> None:
        i = bisect_right(self.inizi, a)
        self.inizi.insert(i, a)
        self.fini.insert(i, b)

    def __iter__(self):
        return iter(zip(self.inizi, self.fini))
