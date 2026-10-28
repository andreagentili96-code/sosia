"""Quickstart: pseudonymise an invented letter locally, pretend an LLM answered, restore the real data.

No network, no model, no API key:  python examples/quickstart.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from sosia import Configurazione, Sessione

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QUI = Path(__file__).resolve().parent
lettera = (QUI / "documents" / "lettera_avvocato.md").read_text(encoding="utf-8")

s = Sessione(Configurazione(seme=7))        # fixed seed: same surrogates at every run (omit it in real use)
finto = s.pseudonimizza(lettera)

print("=== What the cloud LLM would receive ===\n")
print(finto.testo)
print("Replaced:", ", ".join(f"{k} {v}" for k, v in sorted(finto.conteggi.items())))
print(f"Date shift: {s.delta // 7} weeks (weekdays preserved)\n")

# A pretend answer written on the surrogates, as an LLM would: it reuses the fake names, rewrites a surname in
# capitals and computes a new date (the day before the fake deadline).
nomi = {k: v["f"] for k, v in s.unita.items()}
scadenza_finta = dt.date(2026, 10, 25) + dt.timedelta(days=s.delta)
vigilia = (scadenza_finta - dt.timedelta(days=1)).strftime("%d/%m/%Y")
risposta = (f"Riepilogo: la Sig.ra {nomi['anna']} {nomi['rossi']} chiede al Sig. {nomi['rossi'].upper()} "
            f"€ 1.950,00. Conviene pagare entro il {vigilia}, il giorno prima della scadenza.")
print("=== Pretend LLM answer (on surrogates) ===\n")
print(risposta, "\n")

print("=== What you get back ===\n")
print(s.ripristina(risposta).testo, "\n")

# The round trip of the whole letter is byte-for-byte identical.
assert s.ripristina(finto.testo).testo == lettera
print("Round trip of the full letter: identical.")
