"""Sosia: scudo locale per i dati personali fra l'utente e i modelli in cloud.

Uso minimo:
    from sosia import Sessione
    s = Sessione()
    finto = s.pseudonimizza(testo).testo      # va alla cloud
    vero = s.ripristina(risposta).testo        # torna all'utente
"""
from .sessione import Configurazione, Esito, FugaRilevata, RipristinoFlusso, Sessione, SessioneScaduta

__version__ = "0.6.0"
__all__ = ["Sessione", "Configurazione", "Esito", "RipristinoFlusso", "FugaRilevata", "SessioneScaduta",
           "pseudonimizza", "ripristina"]


def pseudonimizza(testo: str, sessione: Sessione | None = None) -> tuple[str, Sessione]:
    s = sessione or Sessione()
    return s.pseudonimizza(testo).testo, s


def ripristina(testo: str, sessione: Sessione) -> str:
    return sessione.ripristina(testo).testo
