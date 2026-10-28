"""Generatori di dati finti realistici e coerenti (controlli validi, stesso formato dell'originale)."""
from __future__ import annotations

import datetime as dt
import re

from . import dati, validatori as V

LETTERE_TARGA = "ABCDEFGHJKLMNPRSTVWXYZ"
ABI_NOTI = ["03069", "02008", "05034", "03032", "01030", "05387", "03062", "03015", "07601", "05696", "06230",
            "03104", "05584", "08327", "03111"]


def stampo(originale: str, canonico: str) -> str:
    """Rimette i caratteri di `canonico` nelle posizioni alfanumeriche di `originale` (spazi e trattini restano).
    Conserva maiuscole/minuscole per posizione. Se le lunghezze non tornano restituisce il canonico."""
    n_alnum = sum(c.isalnum() or c == "*" for c in originale)
    if n_alnum != len(canonico):
        return canonico
    out, k = [], 0
    for c in originale:
        if c.isalnum() or c == "*":
            x = canonico[k]
            out.append(x.lower() if c.islower() else x.upper() if c.isupper() else x)
            k += 1
        else:
            out.append(c)
    return "".join(out)


def cifre_casuali(rng, n: int, prima_non_zero: bool = False) -> str:
    s = "".join(rng.choice("0123456789") for _ in range(n))
    if prima_non_zero and n and s[0] == "0":
        s = rng.choice("123456789") + s[1:]
    return s


def come_classi(rng, s: str, conserva: int = 0) -> str:
    """Stessa struttura: lettere→lettere, cifre→cifre; i primi `conserva` caratteri restano."""
    out = []
    for i, c in enumerate(s):
        if i < conserva:
            out.append(c)
        elif c.isdigit():
            out.append(rng.choice("0123456789"))
        elif c.isalpha():
            x = rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")
            out.append(x if c.isupper() else x.lower())
        else:
            out.append(c)
    return "".join(out)


def finto_iban(rng, reale: str, banca: str = "casuale") -> str:
    s = re.sub(r"[\s-]", "", reale).upper()
    paese, bban = s[:2], s[4:]
    if paese == "IT" and len(bban) == 23:
        abi = bban[1:6] if banca == "mantieni" else rng.choice(ABI_NOTI)
        cab = cifre_casuali(rng, 5, True)
        conto = come_classi(rng, bban[11:])
        cin = V.cin_italiano(abi, cab, conto)
        nuovo = cin + abi + cab + conto
    else:
        nuovo = come_classi(rng, bban, conserva=4 if banca == "mantieni" else 0)
    return paese + V.cifre_iban(paese, nuovo) + nuovo


def finto_piva(rng) -> str:
    primi = cifre_casuali(rng, 7, True) + f"{rng.randint(1, 100):03d}"
    return primi + V.controllo_piva(primi)


def finta_carta(rng, reale: str) -> str:
    c = re.sub(r"\D", "", reale)
    corpo = c[0] + cifre_casuali(rng, len(c) - 2)
    return corpo + V.cifra_luhn(corpo)


def finto_telefono(rng, cifre_naz: str) -> str:
    """Cifre nazionali finte: si conserva il tipo (cellulare 3xx o fisso 0x) e la lunghezza."""
    tieni = 3 if cifre_naz.startswith("3") else 2
    return cifre_naz[:tieni] + cifre_casuali(rng, len(cifre_naz) - tieni)


def finta_targa(rng) -> str:
    L = lambda: rng.choice(LETTERE_TARGA)  # noqa: E731
    return f"{L()}{L()}{cifre_casuali(rng, 3)}{L()}{L()}"


def finto_ip(rng) -> str:
    return ".".join(str(rng.randint(11, 223)) for _ in range(4))


def finta_pratica(rng, reale: str, delta_anni: int) -> str:
    """Cifre casuali, lettere invariate; un anno (19xx/20xx) delimitato si sposta come le date."""
    pezzi = re.split(r"((?<![\d])(?:19|20)\d\d(?![\d]))", reale)
    out = []
    for i, p in enumerate(pezzi):
        if i % 2 == 1 and re.search(r"[/\-.]", reale):
            out.append(str(int(p) + delta_anni))
        else:
            out.append("".join(rng.choice("0123456789") if c.isdigit() else c for c in p))
    return "".join(out)


def finto_documento(rng, reale: str) -> str:
    s = reale
    if re.fullmatch(r"80380\d{15}", s):
        return "80380" + cifre_casuali(rng, 15)
    return come_classi(rng, s, conserva=1 if s[:1].isalpha() else 0)


def finto_numero(rng, reale: str) -> str:
    return cifre_casuali(rng, len(reale), prima_non_zero=reale[0] != "0")


def finto_civico(rng, reale: str) -> str:
    m = re.match(r"(\d+)(.*)", reale)
    if not m:
        return reale
    n = rng.randint(1, max(9, min(200, int(m.group(1)) * 3)))
    return str(n) + m.group(2)


def sillabe_cognome(rng) -> str:
    a = rng.choice(["Bar", "Cor", "Fal", "Gar", "Lan", "Mar", "Nar", "Par", "Ser", "Tor", "Val", "Ber", "Cal", "Dor"])
    b = rng.choice(["ca", "de", "li", "mo", "ro", "si", "ta", "ve", "bel", "gan", "lan", "man"])
    c = rng.choice(["lli", "tti", "ni", "ri", "si", "zzi", "doni", "letti", "rini", "sio"])
    return a + b + c


def finto_comune(rng, escludi: set) -> tuple:
    scelte = [c for c in dati.COMUNI if c[0] not in escludi and c[0] not in dati.ALIAS_COMUNI_ESCLUSI]
    return rng.choice(scelte or dati.COMUNI)


def nascita_finta(nascita: dt.date, delta: int) -> dt.date:
    return nascita + dt.timedelta(days=delta)
