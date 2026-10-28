"""Riga di comando.

  sosia pseudonimizza FILE [-o USCITA] [--sessione NOME] [--fuga] [--aziende]
  sosia ripristina FILE [-o USCITA] --sessione NOME
  sosia sessioni [--pulisci] [--elimina NOME]
  sosia oggi --sessione NOME            (la data di oggi da dichiarare al modello)
  sosia proxy [--porta 8787] [--immagini blocca|lascia]

La mappa vive solo nella cassaforte locale cifrata (DPAPI su Windows, oppure SOSIA_PAROLA)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .cassaforte import Cassaforte
from .sessione import Configurazione, FugaRilevata, Sessione


def _config(a) -> Configurazione:
    return Configurazione(modalita="fuga" if getattr(a, "fuga", False) else "bilanciata",
                          aziende=getattr(a, "aziende", False),
                          sanitari=getattr(a, "sanitari", "segnala"),
                          iban_banca=getattr(a, "iban_banca", "casuale"),
                          scadenza_ore=getattr(a, "scadenza_ore", 168),
                          dichiara_oggi=getattr(a, "dichiara_oggi", False),
                          date={"tutte": True, "nascita": "nascita", "nessuna": False}[getattr(a, "date", "tutte")])


def _sessione(a, cassa: Cassaforte, crea: bool) -> tuple[Sessione, str]:
    from .ner import carica
    ner = carica(getattr(a, "ner", None))
    nome = a.sessione
    if nome and cassa.esiste(nome):
        return cassa.carica(nome, ner), nome
    if not crea:
        sys.exit(f"Sessione «{nome}» inesistente o scaduta.")
    s = Sessione(_config(a), ner=ner)
    return s, nome or s.id


def _uscite_sicure():
    """Console o pipe con una codifica che non ha «⟦» (cp1252 su Windows): sostituisce invece di andare in errore."""
    for flusso in (sys.stdout, sys.stderr):
        try:
            "⟦Δ".encode(flusso.encoding or "ascii")
        except (UnicodeEncodeError, LookupError):
            if hasattr(flusso, "reconfigure"):
                flusso.reconfigure(errors="replace")


def principale(argv=None):
    _uscite_sicure()
    p = argparse.ArgumentParser(prog="sosia", description="Scudo locale per i dati personali verso i modelli in cloud.")
    p.add_argument("--cassaforte", help="cartella delle mappe cifrate (predefinita in %%LOCALAPPDATA%%\\sosia)")
    p.add_argument("-v", "--verboso", action="store_true")
    sp = p.add_subparsers(dest="comando", required=True)

    a = sp.add_parser("pseudonimizza", help="sostituisce i dati personali con dati finti coerenti")
    a.add_argument("file")
    a.add_argument("-o", "--uscita")
    a.add_argument("--sessione", help="nome della sessione (riusata se esiste)")
    a.add_argument("--fuga", action="store_true", help="modalità a prova di fuga: nel dubbio sostituisce")
    a.add_argument("--aziende", action="store_true", help="sostituisce anche le ragioni sociali")
    a.add_argument("--sanitari", choices=["segnala", "sostituisci", "lascia"], default="segnala")
    a.add_argument("--iban-banca", choices=["casuale", "mantieni"], default="casuale")
    a.add_argument("--scadenza-ore", type=int, default=168)
    a.add_argument("--ner", help="riconoscitore a modello facoltativo: gliner[:cartella] o spacy[:modello]")
    a.add_argument("--dichiara-oggi", action="store_true", help="dichiara al modello la data di oggi spostata (Δ ricavabile dal fornitore)")

    b = sp.add_parser("ripristina", help="rimette i dati veri al posto di quelli finti")
    b.add_argument("file")
    b.add_argument("-o", "--uscita")
    b.add_argument("--sessione", required=True)

    c = sp.add_parser("sessioni", help="elenca, pulisce o elimina le sessioni")
    c.add_argument("--pulisci", action="store_true", help="elimina le sessioni scadute")
    c.add_argument("--elimina")

    d = sp.add_parser("oggi", help="istruzioni sulla data di oggi da dare al modello")
    d.add_argument("--sessione", required=True)

    e = sp.add_parser("proxy", help="proxy locale per le API di Anthropic e OpenAI")
    e.add_argument("--porta", type=int, default=8787)
    e.add_argument("--immagini", choices=["blocca", "lascia"], default="blocca")
    e.add_argument("--fuga", action="store_true")
    e.add_argument("--aziende", action="store_true")
    e.add_argument("--senza-nota-oggi", action="store_true", help="non aggiunge alcuna istruzione sulla data di oggi")
    e.add_argument("--dichiara-oggi", action="store_true", help="dichiara la data di oggi spostata invece dei marcatori")
    e.add_argument("--ner")
    e.add_argument("--date", choices=["tutte", "nascita", "nessuna"], default="tutte",
                   help="«nascita» per agenti che lavorano con date vere (calendari, promemoria): si spostano solo le date di nascita")
    e.add_argument("--ner-sistema", action="store_true", help="usa il modello NER anche sul prompt di sistema (più lento)")
    e.add_argument("--ner-budget", type=int, default=20000, help="caratteri nuovi per richiesta analizzati dal modello NER (circa 1 s ogni 1000)")
    e.add_argument("--sessione", default="proxy", help="nome della sessione predefinita")
    e.add_argument("--anthropic", default="https://api.anthropic.com", help="indirizzo del fornitore Anthropic (prove)")
    e.add_argument("--registro-uscite", help="file in cui annotare il testo (già pseudonimizzato) inviato alla cloud: solo per le prove")
    e.add_argument("--openai", default="https://api.openai.com", help="indirizzo del fornitore OpenAI (prove)")

    a_ = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a_.verboso else logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    cassa = Cassaforte(a_.cassaforte)

    if a_.comando == "pseudonimizza":
        from .formati import elabora_file
        s, nome = _sessione(a_, cassa, crea=True)
        try:
            uscita, rapporto = elabora_file(a_.file, a_.uscita, s, "pseudonimizza")
        except FugaRilevata as err:
            sys.exit(f"BLOCCATO: {err}. Nessun file scritto.")
        cassa.salva(s, nome)
        print(f"File finto: {uscita}")
        print(f"Sessione: {nome} (scade {s.scadenza[:16].replace('T', ' ')} UTC)")
        print("Sostituzioni: " + ", ".join(f"{k} {v}" for k, v in sorted(rapporto.conteggi.items())))
        for x in rapporto.avvisi:
            print(f"Avviso: {x}")
        print(s.istruzioni_oggi())
    elif a_.comando == "ripristina":
        from .formati import elabora_file
        s, nome = _sessione(a_, cassa, crea=False)
        uscita, rapporto = elabora_file(a_.file, a_.uscita, s, "ripristina")
        print(f"File ripristinato: {uscita}")
        print("Ripristini: " + ", ".join(f"{k} {v}" for k, v in sorted(rapporto.conteggi.items())))
        if rapporto.incerti:
            print(f"ATTENZIONE: {rapporto.incerti} punti incerti non ripristinati: controllare a mano.")
    elif a_.comando == "sessioni":
        if a_.elimina:
            print("eliminata" if cassa.elimina(a_.elimina) else "non trovata")
        elif a_.pulisci:
            print(f"Sessioni scadute eliminate: {cassa.pulisci()}")
        else:
            print(json.dumps(cassa.elenco(), ensure_ascii=False, indent=2))
    elif a_.comando == "oggi":
        s, _ = _sessione(a_, cassa, crea=False)
        print(s.istruzioni_oggi())
    elif a_.comando == "proxy":
        import uvicorn
        from .ner import carica
        from .proxy import Scudo, crea_app, gettone_locale
        import threading
        # Il servizio risponde SUBITO con le sole regole; il modello si carica e si scalda in sottofondo
        # (prima richiesta mai in attesa del modello, mai in errore).
        cfg = _config(a_)
        cfg.ner_modo = "auto"
        scudo = Scudo(cassa, cfg, None)
        if a_.ner:
            scudo.stato_ner = "caricamento"

            def carica_in_sottofondo():
                try:
                    ner = carica(a_.ner)
                    ner.riconosci("Il sig. Mario Rossi abita a Squinzano con la figlia Xiomara.")  # riscaldamento
                    scudo.imposta_ner(ner, "pronto")
                except Exception as e:  # restano le regole
                    scudo.stato_ner = "errore: " + type(e).__name__
            threading.Thread(target=carica_in_sottofondo, daemon=True).start()
        token = gettone_locale(cassa.cartella.parent)
        app = crea_app(scudo, anthropic=a_.anthropic, openai=a_.openai, immagini=a_.immagini, nota_oggi=not a_.senza_nota_oggi, token=token,
                       ner_sistema=a_.ner_sistema, sessione_predefinita=a_.sessione, registro_uscite=a_.registro_uscite,
                       ner_budget=a_.ner_budget)
        print(f"Sosia in ascolto su http://127.0.0.1:{a_.porta} (gettone locale in {cassa.cartella.parent / 'gettone.txt'})")
        uvicorn.run(app, host="127.0.0.1", port=a_.porta, log_level="warning")


if __name__ == "__main__":
    principale()
