"""JSON: si trasformano i valori stringa (le chiavi restano). Le stringhe brevi senza contesto ricevono
il contesto della chiave («nome», «cognome», «citta»), così «"cognome": "Rossi"» viene riconosciuto."""
from __future__ import annotations

import json

from ..dati import norm

CHIAVI_PERSONA = {"nome": "nome", "first_name": "nome", "firstname": "nome", "given_name": "nome",
                  "cognome": "cognome", "last_name": "cognome", "lastname": "cognome", "surname": "cognome",
                  "family_name": "cognome"}
CHIAVI_CITTA = {"citta", "città", "comune", "city", "luogo_nascita", "luogo_di_nascita", "residenza"}


def _registra(o, s):
    if isinstance(o, dict):
        nome = next((v for k, v in o.items() if CHIAVI_PERSONA.get(norm(k)) == "nome" and isinstance(v, str)), None)
        cognome = next((v for k, v in o.items() if CHIAVI_PERSONA.get(norm(k)) == "cognome" and isinstance(v, str)), None)
        if nome or cognome:
            s.registra_persona(nome, cognome)
        for k, v in o.items():
            if norm(k) in CHIAVI_CITTA and isinstance(v, str) and v.strip():
                s._citta(v.strip())
            _registra(v, s)
    elif isinstance(o, list):
        for x in o:
            _registra(x, s)


def trasforma(o, verso):
    if isinstance(o, str):
        return verso.stringa(o)
    if isinstance(o, list):
        return [trasforma(x, verso) for x in o]
    if isinstance(o, dict):
        return {k: trasforma(v, verso) for k, v in o.items()}
    return o


def elabora(dati: bytes, verso, est: str):
    o = json.loads(dati.decode("utf-8-sig"))
    if verso.avanti:
        _registra(o, verso.s)
    return json.dumps(trasforma(o, verso), ensure_ascii=False, indent=2).encode("utf-8"), est
