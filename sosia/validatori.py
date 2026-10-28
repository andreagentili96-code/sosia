"""Validatori e calcolo dei caratteri di controllo: codice fiscale, partita IVA, IBAN (con CIN italiano), Luhn."""
from __future__ import annotations

import datetime as _dt
import re

_DISPARI = {**{str(i): v for i, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
            **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                       [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))}
OMOCODIA = "LMNPQRSTUV"
MESI_CF = "ABCDEHLMPRST"
RE_CF = re.compile(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]")


def _pari(c: str) -> int:
    return int(c) if c.isdigit() else ord(c) - 65


def controllo_cf(primi15: str) -> str:
    s = primi15.upper()
    tot = sum(_DISPARI[c] if i % 2 == 0 else _pari(c) for i, c in enumerate(s[:15]))
    return chr(65 + tot % 26)


def _cifra(c: str) -> int:
    return int(c) if c.isdigit() else OMOCODIA.index(c)


def cf_valido(cf: str) -> bool:
    s = re.sub(r"\s", "", cf).upper()
    if not RE_CF.fullmatch(s):
        return False
    g = _cifra(s[9]) * 10 + _cifra(s[10])
    if not (1 <= g <= 31 or 41 <= g <= 71):
        return False
    return controllo_cf(s[:15]) == s[15]


def decodifica_cf(cf: str, oggi: _dt.date | None = None) -> dict | None:
    """Data di nascita, sesso e codice del comune ricavati dal codice fiscale (se la forma è corretta)."""
    s = re.sub(r"\s", "", cf).upper()
    if not RE_CF.fullmatch(s):
        return None
    try:
        aa = _cifra(s[6]) * 10 + _cifra(s[7])
        mese = MESI_CF.index(s[8]) + 1
        g = _cifra(s[9]) * 10 + _cifra(s[10])
        sesso = "F" if g > 40 else "M"
        g = g - 40 if g > 40 else g
        oggi = oggi or _dt.date.today()
        anno = 2000 + aa if 2000 + aa <= oggi.year else 1900 + aa
        nascita = _dt.date(anno, mese, g)
        comune = s[11] + "".join(str(_cifra(c)) for c in s[12:15])
    except (ValueError, IndexError):
        return None
    return {"nascita": nascita, "sesso": sesso, "comune": comune}


def _consonanti(s: str) -> str:
    return "".join(c for c in s if c.isalpha() and c not in "AEIOU")


def _vocali(s: str) -> str:
    return "".join(c for c in s if c in "AEIOU")


def _pulisci(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.upper())
    return "".join(c for c in s if "A" <= c <= "Z")


def codice_cognome(cognome: str) -> str:
    s = _pulisci(cognome)
    return (_consonanti(s) + _vocali(s) + "XXX")[:3]


def codice_nome(nome: str) -> str:
    s = _pulisci(nome)
    c = _consonanti(s)
    if len(c) >= 4:
        return c[0] + c[2] + c[3]
    return (c + _vocali(s) + "XXX")[:3]


def genera_cf(cognome: str, nome: str, nascita: _dt.date, sesso: str, comune: str) -> str:
    g = nascita.day + (40 if sesso == "F" else 0)
    primi = f"{codice_cognome(cognome)}{codice_nome(nome)}{nascita.year % 100:02d}{MESI_CF[nascita.month - 1]}{g:02d}{comune}"
    return primi + controllo_cf(primi)


# ------------------------------------------------------------------ partita IVA
def controllo_piva(primi10: str) -> str:
    tot = 0
    for i, ch in enumerate(primi10[:10]):
        d = int(ch)
        if i % 2 == 0:
            tot += d
        else:
            x = d * 2
            tot += x - 9 if x > 9 else x
    return str((10 - tot % 10) % 10)


def piva_valida(p: str) -> bool:
    s = re.sub(r"^IT|\s", "", p.upper())
    return bool(re.fullmatch(r"\d{11}", s)) and not s.startswith("0000000") and controllo_piva(s) == s[10]


# ------------------------------------------------------------------ IBAN
LUNGHEZZE_IBAN = {"IT": 27, "SM": 27, "VA": 22, "DE": 22, "FR": 27, "ES": 24, "GB": 22, "CH": 21, "AT": 20,
                  "BE": 16, "NL": 18, "PT": 25, "IE": 22, "LU": 20, "MC": 27, "PL": 28, "SI": 19, "HR": 21,
                  "GR": 27, "RO": 24, "LT": 20, "LV": 21, "EE": 20, "FI": 18, "SE": 24, "DK": 18, "NO": 15,
                  "CZ": 24, "SK": 24, "HU": 28, "MT": 31, "CY": 28, "BG": 22, "LI": 21, "IS": 26, "AL": 28}


def _mod97(s: str) -> int:
    r = 0
    for c in s:
        for d in (c if c.isdigit() else str(ord(c) - 55)):
            r = (r * 10 + int(d)) % 97
    return r


def iban_valido(iban: str) -> bool:
    s = re.sub(r"[\s-]", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    att = LUNGHEZZE_IBAN.get(s[:2])
    if att and len(s) != att:
        return False
    return _mod97(s[4:] + s[:4]) == 1


def cifre_iban(paese: str, bban: str) -> str:
    return f"{98 - _mod97(bban.upper() + paese.upper() + '00'):02d}"


def cin_italiano(abi: str, cab: str, conto: str) -> str:
    """CIN del BBAN italiano: stesse tabelle dispari/pari del codice fiscale, su ABI+CAB+conto (22 caratteri)."""
    s = (abi + cab + conto).upper()
    tot = sum(_DISPARI[c] if i % 2 == 0 else _pari(c) for i, c in enumerate(s))
    return chr(65 + tot % 26)


# ------------------------------------------------------------------ carte
def luhn_valido(numero: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", numero)]
    if not 12 <= len(d) <= 19:
        return False
    tot = 0
    for i, x in enumerate(reversed(d)):
        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9
        tot += x
    return tot % 10 == 0


def cifra_luhn(senza_controllo: str) -> str:
    for c in "0123456789":
        if luhn_valido(senza_controllo + c):
            return c
    raise ValueError("impossibile")
