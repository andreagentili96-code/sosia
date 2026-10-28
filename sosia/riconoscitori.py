"""Riconoscitori a regole: schemi con controllo (CF, IBAN, P.IVA, carte), contesto (documenti, pratiche,
indirizzi) e dizionari (nomi, cognomi, comuni). Restituiscono intervalli; non sostituiscono nulla."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import dati, dati_en as _DE, validatori as V
from .dati import norm
from .intervalli import Intervalli

dati.NON_NOMI.update(_DE.TITOLI_EN)
from .prefiltro import LESSICO as _LESSICO_PRE  # noqa: E402
from .prefiltro import PAROLE_COMUNI as _PAROLE_COMUNI  # noqa: E402

PRIORITA = {"CALCOLO": 12, "CODICE": 5, "CAP": 6, "EMAIL": 10, "IBAN": 10, "CF": 10, "URL": 10, "CARTA": 9, "PIVA": 9, "IP": 9, "DOCUMENTO": 8,
            "TELEFONO": 8, "TARGA": 7, "PRATICA": 7, "DATA": 6, "INDIRIZZO": 6, "CAP_CITTA": 6, "AZIENDA": 5,
            "NOME": 4, "COGNOME": 4, "INIZIALE": 4, "PERSONA": 4, "CITTA": 3, "SANITARIO": 2, "NUMERO": 1,
            "SSN": 9, "ITIN": 9, "NINO": 9, "NHS": 9, "ROUTING": 9, "SORTCODE": 8, "CONTO": 8, "PASSAPORTO": 8,
            "PATENTE": 8, "VIN": 8, "CATASTO": 7, "VIA": 6, "CIVICO": 3}


@dataclass
class Span:
    inizio: int
    fine: int
    tipo: str
    testo: str
    confidenza: float = 1.0
    meta: dict = field(default_factory=dict)


@dataclass
class PersonaCandidata:
    inizio: int
    fine: int
    parole: list  # [(inizio, fine, testo)]
    genere: str | None
    confidenza: float
    fonte: str
    ruoli: list | None = None  # ruoli già decisi dalla regola: [(ruolo, inizio, fine, None)]


_UP = "A-ZÀ-ÖØ-Ý"
_LO = "a-zß-öø-ÿ"
PAROLA_NOME = re.compile(
    rf"(?:(?:De|Di|Del|Della|Dello|Dei|Degli|Da|Dal|Dalla|La|Lo|Li|Le|Lu|Mac|Van|Von|El|Ben|Abu|Bin|Ould|EL|DE|DI|DEL|DELLA|DA|DAL|LA|LO|LI)\s+)?"
    rf"(?:(?:D|L|Dell|Dall|Sant|DELL|DALL)['’])?(?:[{_UP}][{_LO}]+(?:['’][{_UP}][{_LO}]+)?|[{_UP}]{{2,}}(?:['’][{_UP}]+)?)"
    rf"(?:-[{_UP}][{_LO}]+|-[{_UP}]{{2,}})?(?![\w])")
# Elenchi curati (servono anche da soli) e dizionari estesi (solo accanto a un altro indizio: titolo, etichetta,
# nome + cognome). Dai dizionari estesi si tolgono le parole comuni italiane e inglesi e le voci di due lettere.
_FILTRO_DIZ = _LESSICO_PRE | _DE.COMMON_WORDS | dati.NON_NOMI
NOMI_BASE = {norm(x) for x in dati.NOMI_M + dati.NOMI_F}
COGNOMI_BASE = {norm(x) for x in dati.COGNOMI}
NOMI_M = {norm(x) for x in dati.NOMI_M} | {x for x in dati.NOMI_EXTRA_M if len(x) >= 3 and x not in _FILTRO_DIZ}
NOMI_F = {norm(x) for x in dati.NOMI_F} | {x for x in dati.NOMI_EXTRA_F if len(x) >= 3 and x not in _FILTRO_DIZ}
NOMI_M |= {x for x in dati.NOMI_UFF if len(x) >= 3 and x not in _FILTRO_DIZ and x not in _PAROLE_COMUNI and x not in NOMI_F}
NOMI = NOMI_M | NOMI_F
COGNOMI = COGNOMI_BASE | {x for x in dati.COGNOMI_EXTRA | dati.COGNOMI_UFF if len(x) >= 3 and x not in _FILTRO_DIZ
                          and (x in dati.COGNOMI_EXTRA or x not in _PAROLE_COMUNI)}
COMUNI = {norm(c[0]): c for c in dati.COMUNI}
_LUOGHI_INTITOLATI = {"via", "viale", "piazza", "corso", "largo", "liceo", "istituto", "scuola", "ospedale",
                      "policlinico", "aeroporto", "stadio", "teatro", "fondazione", "premio", "università", "universita",
                      "ponte", "galleria", "museo", "centro", "itis", "ipsia", "convitto", "collegio", "caserma",
                      "piazzale", "lungomare", "stazione", "parco", "biblioteca", "auditorium", "palazzo"}
_PREPOSIZIONI_SANTI = {"san", "santa", "santo", "sant'", "s.", "ss.", "beata", "beato", "madonna", "maria"}
RE_FORMA_DOPO = re.compile(r"(?:[ \t]+[A-ZÀ-Ý][\w&'’.-]*){0,3}[ \t]*(?:" + dati.FORME_SOCIETARIE + r")(?![\w])")
RE_TITOLO = re.compile(r"(?<![\w.])" + dati.TITOLI + r"\s+")  # «explanation. The»: «on.» non è un titolo
RE_INDIZIO = re.compile(r"(?<![\w])" + dati.INDIZI_PERSONA + r"[\s:,]+(?:" + dati.TITOLI + r"\s+)?", re.I)
RE_ETICHETTA = re.compile(r"(?:^|(?<=\n)|(?<=\|)|(?<=\t)|(?<=  ))[ \t]*" + dati.ETICHETTE_PERSONA + r"[ \t]*[:\t][ \t]*", re.I | re.M)


def _riga_maiuscola(testo: str, i: int) -> bool:
    a = testo.rfind("\n", 0, i) + 1
    b = testo.find("\n", i)
    riga = testo[a:b if b >= 0 else len(testo)]
    lettere = [c for c in riga if c.isalpha()]
    return len(lettere) > 8 and sum(c.isupper() for c in lettere) / len(lettere) > 0.8


def genere_nome(parola: str) -> str | None:
    n = norm(parola)
    if n in dati.AMBIGUI_GENERE:
        return dati.AMBIGUI_GENERE[n]
    if n in NOMI_M and n not in NOMI_F:
        return "M"
    if n in NOMI_F and n not in NOMI_M:
        return "F"
    return None


def _non_nome(parola: str) -> bool:
    n = norm(parola)
    return (n in dati.NON_NOMI or n.rstrip(".") in dati.NON_NOMI or n in COMUNI or n in _DE.COMMON_WORDS
            or n in _PAROLE_COMUNI)


def leggi_parole(testo: str, pos: int, massimo: int = 3, stesso_rigo: bool = True) -> list:
    """Parole maiuscole consecutive a partire da pos (separate da spazi semplici)."""
    parole = []
    i = pos
    while len(parole) < massimo:
        m = PAROLA_NOME.match(testo, i)
        if not m:
            break
        w = m.group(0)
        if _non_nome(w) and not (parole and norm(w) in COMUNI and norm(w) in COGNOMI):
            break  # «Pasquale Ferrara»: dopo un nome, un comune che è anche cognome è il cognome
        parole.append((m.start(), m.end(), w))
        j = m.end()
        sp = re.match(r"[ \t]{1,2}" if stesso_rigo else r"\s{1,2}", testo[j:])
        if not sp:
            break
        i = j + sp.end()
    return parole


def _inizio_frase(testo: str, i: int) -> bool:
    prima = testo[max(0, i - 4):i]
    return i == 0 or bool(re.search(r"(?:[.!?:;\n\"«(]\s*|^\s*)$", prima)) or prima.endswith("\n")


def _precedente(testo: str, i: int) -> str:
    m = re.search(r"([\w'’.]+)\s+$", testo[max(0, i - 20):i])
    return norm(m.group(1)) if m else ""


def _genere_contesto(testo: str, inizio: int) -> str | None:
    prima = testo[max(0, inizio - 30):inizio].lower()
    for t in dati.TITOLI_FEMMINILI:
        if t in prima:
            return "F"
    if re.search(r"\b(?:sig\.|signor|dott\.|dottor|prof\.|il sottoscritto|nato|mr\.)\s*$", prima):
        return "M"
    return None


RE_SENSIBILE = re.compile(
    r"(?i)\b(?:diagnosi|anamnesi|referto|terapia|paziente|ricovero|dimissione|cartella\s+clinica|esame\s+obiettivo|posologia|"
    r"patient|diagnosis|discharge|medication|prescri\w+|clinical|symptoms?|allerg\w+|psichiatr\w+|psycholog\w+|"
    r"tribunale|ricorso|sentenza|decreto|udienza|querela|denuncia|citazione|avv\.|imputat\w+|convenut\w+|attore|"
    r"court|plaintiff|defendant|petitioner|respondent|claimant|hearing|witness|affidavit|attorney|solicitor|probate|custody)\b")


def testo_sensibile(testo: str) -> bool:
    """Testi sanitari o legali: almeno tre parole diverse del lessico clinico o giudiziario."""
    return len({m.group(0).lower() for m in RE_SENSIBILE.finditer(testo)}) >= 3


# ------------------------------------------------------------------ persone
def candidati_persone(testo: str, modalita: str = "bilanciata") -> list[PersonaCandidata]:
    out: list[PersonaCandidata] = []

    def aggiungi(parole, fonte, conf, genere=None):
        if not parole:
            return
        if len(parole) >= 2 and fonte in ("dizionario", "cognome+nome") and norm(" ".join(p[2] for p in parole)) in dati.LUOGHI_IT:
            return  # «San Giovanni», «Santa Croce»: un luogo, non una persona
        pm_ = re.search(r"([\w'’]+)[ \t]+$", testo[max(0, parole[0][0] - 25):parole[0][0]])
        if pm_ and norm(pm_.group(1) + " " + " ".join(p[2] for p in parole)) in dati.LUOGHI_IT:
            return  # «Reggio Emilia»: «Emilia» qui è un pezzo del nome della città
        # Scarta persone celebri (vie, scuole, ospedali) se l'indizio è debole.
        if any(norm(p[2]) in dati.CELEBRI for p in parole) and _precedente(testo, parole[0][0]) in _LUOGHI_INTITOLATI:
            return
        if _precedente(testo, parole[0][0]) in _PREPOSIZIONI_SANTI:
            return
        if RE_FORMA_DOPO.match(testo, parole[-1][1]):
            return
        g = genere or _genere_contesto(testo, parole[0][0])
        out.append(PersonaCandidata(parole[0][0], parole[-1][1], parole, g, conf, fonte))

    for m in RE_TITOLO.finditer(testo):
        t = m.group(0).strip().lower()
        g = "F" if any(t.startswith(x) for x in dati.TITOLI_FEMMINILI) else None
        aggiungi(leggi_parole(testo, m.end()), "titolo", 0.95, g)
    for m in RE_INDIZIO.finditer(testo):
        parole = leggi_parole(testo, m.end())
        if not parole:
            continue
        forte = len(parole) >= 2 or any(norm(p[2]) in NOMI or norm(p[2]) in COGNOMI for p in parole)
        if forte or modalita == "fuga":
            aggiungi(parole, "indizio", 0.9 if forte else 0.6)
    for m in RE_ETICHETTA.finditer(testo):
        parole = leggi_parole(testo, m.end(), massimo=4)
        if parole:
            aggiungi(parole, "etichetta", 0.9)
    # Dizionario: un nome di battesimo vicino a una parola maiuscola.
    for m in PAROLA_NOME.finditer(testo):
        w = m.group(0)
        n = norm(w)
        if n not in NOMI or " " in w:
            continue
        if w.isupper() and n not in NOMI_BASE and _riga_maiuscola(testo, m.start()):
            continue  # titoli in maiuscolo («DATI CATASTALI»): solo i nomi dell'elenco curato
        dopo = leggi_parole(testo, m.end() + 1, massimo=2) if testo[m.end():m.end() + 1] == " " else []
        prima = None
        pm = re.search(rf"((?:(?:De|Di|Del|Della|Lo|La|Li|Da|Dal|Dalla|DE|DI|DEL|DELLA|LO|LA|LI|DA)[ \t])?(?:D['’]|Dall['’]|Dell['’]|DALL['’]|DELL['’])?"
                       rf"(?:[{_UP}][{_LO}]+|[{_UP}]{{2,}})(?:['’][{_UP}][{_LO}]+)?)[ \t]$", testo[max(0, m.start() - 40):m.start()])
        if pm and not _non_nome(pm.group(1)):
            prima = (m.start() - len(pm.group(0)), m.start() - 1, pm.group(1))
        if dopo and norm(dopo[0][2]) not in NOMI | dati.NON_NOMI:
            aggiungi([(m.start(), m.end(), w)] + dopo[:1 if norm(dopo[0][2]) in NOMI else 2][:2], "dizionario", 0.85)
        elif dopo and norm(dopo[0][2]) in NOMI and len(dopo) > 1:
            aggiungi([(m.start(), m.end(), w)] + dopo, "dizionario", 0.85)  # «Maria Grazia Esposito»
        elif prima and (w.isupper() or prima[2].isupper() or norm(prima[2]) in COGNOMI):
            aggiungi([prima, (m.start(), m.end(), w)], "dizionario", 0.8)  # «ROSSI MARIO», «Rossi Mario»
        elif n not in dati.NOMI_PAROLA and n in NOMI_BASE and (not _inizio_frase(testo, m.start()) or modalita == "fuga"):
            aggiungi([(m.start(), m.end(), w)], "nome-solo", 0.7)
        elif n not in dati.NOMI_PAROLA and n in NOMI_BASE and re.match(r"[ \t]*[,:]", testo[m.end():]):
            aggiungi([(m.start(), m.end(), w)], "nome-solo", 0.7)  # «Giulia, ti scrivo…»
    # Cognomi frequenti da soli (non parole comuni).
    for m in PAROLA_NOME.finditer(testo):
        w = m.group(0)
        n = norm(w)
        if n in COGNOMI_BASE and n not in NOMI and (n not in dati.COGNOMI_PAROLA or modalita == "fuga"):
            if _inizio_frase(testo, m.start()) and n in dati.COGNOMI_PAROLA:
                continue
            dopo = leggi_parole(testo, m.end() + 1, massimo=1) if testo[m.end():m.end() + 1] == " " else []
            if dopo and norm(dopo[0][2]) not in COGNOMI:
                aggiungi([(m.start(), m.end(), w)] + dopo, "cognome+nome", 0.75)
            else:
                aggiungi([(m.start(), m.end(), w)], "cognome", 0.75)
    # Chat esportate: «[08/10/2025, 18:36] Fede: …» — chi parla è una persona.
    for m in RE_CHAT.finditer(testo):
        parole = leggi_parole(testo, m.start("chi"), massimo=3)
        if parole:
            aggiungi(parole, "chat", 0.9)
        elif _nome_minuscolo(m.group("chi").strip()):  # «[08/10/25, 18:36] marco: …»
            a = m.start("chi") + m.group("chi").find(m.group("chi").strip())
            w = m.group("chi").strip()
            out.append(PersonaCandidata(a, a + len(w), [(a, a + len(w), w)], None, 0.85, "minuscolo",
                                        [("nome", a, a + len(w), None)]))
    # nomi scritti in minuscolo dopo un saluto o una parentela: «ciao marco», «grazie giulia», «zia carmela», «hi tom»
    for m in RE_CUE_MINUSCOLO.finditer(testo):
        w = m.group("n")
        parentela = re.match(r"(?i)zi[oa]|nonn[oa]|cugin[oa]|uncle|aunt|auntie|nan|grand", m.group(0)) is not None
        if _nome_minuscolo(w, parentela):
            out.append(PersonaCandidata(m.start("n"), m.end("n"), [(m.start("n"), m.end("n"), w)], None, 0.8, "minuscolo",
                                        [("nome", m.start("n"), m.end("n"), None)]))
    for a, b in soprannomi(testo):
        aggiungi([(a, b, testo[a:b])], "soprannome", 0.9)
    # parentela: «assistita dal figlio Dmytro», «her son Kevin», «la moglie Halina»
    for m in RE_PARENTELA.finditer(testo):
        parole = leggi_parole(testo, m.end(), massimo=3)
        if parole and not (len(parole) == 1 and norm(parole[0][2]) in _DE.COMMON_WORDS):
            aggiungi(parole, "indizio", 0.85)
    # saluti e firme su una riga da sola: «Mo,» in apertura, «Rhi» dopo «Cheers,»
    for m in RE_RIGA_UNA_PAROLA.finditer(testo):
        w = m.group("n")
        if _non_nome(w) or norm(w) in _DE.COMMON_WORDS or norm(w) in _LESSICO_PRE:
            continue
        precedente = testo[:m.start()].rstrip().rsplit("\n", 1)[-1]
        if m.group("virgola") or RE_CONGEDO.search(precedente) or (len(w) <= 4 and m.end() >= len(testo.rstrip()) - 2):
            aggiungi([(m.start("n"), m.end("n"), w)], "firma", 0.8)
    for m in RE_CONGEDO_IN_RIGA.finditer(testo):  # «Cheers, Mo», «Un saluto, Fede»
        w = m.group("n")
        if not (_non_nome(w) or norm(w) in _DE.COMMON_WORDS):
            aggiungi([(m.start("n"), m.end("n"), w)], "firma", 0.8)
    # «Dwayne "Deej" Hunter», «Immacolata (Imma) Ruocco»: nome, soprannome, cognome
    for m in RE_NOME_SOPRANNOME_COGNOME.finditer(testo):
        a, c = m.group("a"), m.group("c")
        if _non_nome(a) or _non_nome(c.split()[-1]) or norm(c.split()[-1]) in _DE.COMMON_WORDS:
            continue
        if norm(a) not in NOMI and norm(c.split()[-1]) not in COGNOMI:
            continue
        parole = [(m.start("a"), m.end("a"), a), (m.start("c"), m.end("c"), c)]
        out.append(PersonaCandidata(m.start("a"), m.end("a"), parole, _genere_contesto(testo, m.start()), 0.9, "soprannome",
                                    [("nome", m.start("a"), m.end("a"), None), ("cognome", m.start("c"), m.end("c"), None)]))
    # «Kenji and Ruth Nakagawa», «Patrick and Colleen O'Donnell»: il primo nome porta lo stesso cognome
    for m in RE_COPPIA_NOMI.finditer(testo):
        a, b, c = m.group("a"), m.group("b"), m.group("c")
        if not (norm(b) in NOMI and (norm(a) in NOMI or norm(c) in COGNOMI)) or _non_nome(a) or _non_nome(c):
            continue
        parole = [(m.start("a"), m.end("a"), a), (m.start("c"), m.end("c"), c)]
        out.append(PersonaCandidata(m.start("a"), m.end("a"), parole, None, 0.85, "coppia",
                                    [("nome", m.start("a"), m.end("a"), None), ("cognome", m.start("c"), m.end("c"), None)]))
    # «G. Rosa, consigliere», «dott. G. Righetti», «C. G. Okafor»: iniziali e poi un cognome, anche se è una parola
    for m in RE_INIZIALI_COGNOME.finditer(testo):
        c = m.group("c")
        ultimo = c.split()[-1]
        if _precedente(testo, m.start()) in _PREPOSIZIONI_SANTI or m.group("i").strip().upper() in ("S.", "SS."):
            continue
        conosciuto = norm(c) in COGNOMI or norm(ultimo) in COGNOMI or norm(ultimo) in NOMI
        if not conosciuto and (_non_nome(ultimo) or norm(ultimo) in _DE.COMMON_WORDS):
            continue
        if not conosciuto and not RE_TITOLO.search(testo[max(0, m.start() - 12):m.start() + 1]) and not re.match(r"[ \t]*[,;)\n]", testo[m.end():]):
            continue
        out.append(PersonaCandidata(m.start("c"), m.end("c"), [(m.start("c"), m.end("c"), c)], None, 0.85, "iniziale",
                                    [("cognome", m.start("c"), m.end("c"), None)]))
    if modalita == "fuga":
        # Ogni sequenza maiuscola a metà frase che non è una parola nota è trattata come nome proprio.
        for m in PAROLA_NOME.finditer(testo):
            w = m.group(0)
            if _inizio_frase(testo, m.start()) or _non_nome(w) or len(w) < 3:
                continue
            if w.isupper() and (len(w) <= 4 or _riga_maiuscola(testo, m.start())):
                continue  # sigle (ASL, INPS, RG) e intestazioni in maiuscolo («LETTERA DI DIMISSIONE»)
            ultima = re.split(r"[ '’]", w)[-1]
            if (not ultima or _non_nome(ultima) or norm(ultima) in _DE.COMMON_WORDS or norm(w) in dati.LUOGHI_IT
                    or norm(w) in _DE.LUOGHI_EN or norm(ultima) in _PAROLE_COMUNI):
                continue  # «DI DIMISSIONE», «SOLICITOR'S», «California»
            aggiungi([(m.start(), m.end(), w)], "fuga", 0.5)
    return out


RE_NOME_SOPRANNOME_COGNOME = re.compile(
    rf"(?<![\w])(?P<a>[{_UP}][{_LO}'’-]+)[ \t]+(?:[\"“«][^\"”»\n]{{1,20}}[\"”»]|\([ \t]*[\"“]?[{_UP}][^()\n]{{0,18}}?[\"”]?[ \t]*\))[ \t]+"
    rf"(?P<c>(?:(?:Van|van|Von|von|De|de|Der|der|Den|den|Da|Di|Del|Della|Dalla|Lo|La|Le|Mac|O['’])[ \t]+)*"
    rf"(?:Mc|Mac|O['’]|D['’])?[{_UP}][{_LO}'’]+(?:-[{_UP}][{_LO}'’]+)?)(?![\w])")
RE_COPPIA_NOMI = re.compile(rf"(?<![\w])(?P<a>[{_UP}][{_LO}-]+)[ \t]+(?:and|e|&)[ \t]+(?P<b>[{_UP}][{_LO}-]+)[ \t]+"
                            rf"(?P<c>(?:Mc|Mac|O['’]|D['’])?[{_UP}][{_LO}'’]+(?:-[{_UP}][{_LO}'’]+)?)(?![\w])")
RE_INIZIALI_COGNOME = re.compile(rf"(?<![\w.])(?P<i>(?:[A-Z]\.[ \t]?){{1,3}})(?P<c>(?:(?:Lo|La|Li|De|Di|Del|Della|Dalla|Van|Mc)[ \t])?"
                                 rf"(?:Mc|Mac|O['’]|D['’])?[{_UP}][{_LO}'’]{{2,}}(?:-[{_UP}][{_LO}'’]+)?)(?![\w]|\.\w)")
RE_CUE_MINUSCOLO = re.compile(r"(?i:\b(?:ciao|grazie|ehi|hey|hi|hello|thanks|thx|cheers|dai|saluta(?:mi)?|auguri|bravo|brava|"
                              r"complimenti|zio|zia|nonno|nonna|cugino|cugina|uncle|aunt|auntie|nan|grandpa|grandma)\b)[ \t]*,?[ \t]+"
                              r"(?P<n>[a-zà-ÿ][a-zà-ÿ'’]{2,14})(?![\w'’])")


_NOMI_EN_BASE = {norm(x) for x in list(_DE.FIRST_M) + list(_DE.FIRST_F)}


def _nome_minuscolo(w: str, parentela: bool = False) -> bool:
    """«marco», «giulia», «tom»: un nome degli elenchi curati scritto in minuscolo che non è anche una parola comune.
    Dopo una parentela («zia carmela») valgono anche i nomi che sono parole."""
    n = norm(w)
    return (w.islower() and " " not in w and (n in NOMI_BASE or n in _NOMI_EN_BASE) and n not in _PAROLE_COMUNI
            and n not in _LESSICO_PRE and n not in _DE.COMMON_WORDS and n not in dati.NON_NOMI
            and (parentela or n not in dati.NOMI_PAROLA))


RE_CHAT = re.compile(r"^\[[^\]\n]{6,30}\][ \t]*(?P<chi>[^:\n]{2,40}):", re.M)
RE_PARENTELA = re.compile(r"(?<![\w])(?i:(?:(?:dal(?:la)?|del(?:la)?|il|la|al(?:la)?|suo|sua|his|her|their|my|our)\s+|(?=zi[oa]\s|nonn[oa]\s|cugin[oa]\s|mamma\s|papà\s|nipote\s))"
                          r"(?:figli[oa]|moglie|marito|madre|padre|fratello|sorella|nipote|nonn[oa]|zi[oa]|cognat[oa]|suocer[oa]|cugin[oa]|mamma|papà|"
                          r"compagn[oa]|fidanzat[oa]|convivente|badante|son|daughter|wife|husband|mother|father|brother|sister|"
                          r"grandson|granddaughter|nephew|niece|uncle|aunt|cousin|partner|fianc[ée]e?|carer|stepson|stepdaughter))"
                          r"[ \t]+(?=[A-ZÀ-Ý])")
RE_RIGA_UNA_PAROLA = re.compile(r"(?m)^[ \t>]*(?P<n>[A-ZÀ-Ý][a-zà-ÿ'’-]{1,14})(?P<virgola>,)?[ \t]*$")
RE_CONGEDO = re.compile(r"(?i)(?:cheers|thanks|thank\s+you|regards|best(?:\s+wishes)?|cordiali\s+saluti|saluti|un\s+saluto|"
                        r"grazie|a\s+presto|ciao|love|yours|sincerely|xx?)[ \t!,.]*$")
RE_CONGEDO_IN_RIGA = re.compile(r"(?i:\b(?:cheers|thanks|regards|best|ciao|grazie|un\s+saluto|saluti))[ \t]*,[ \t]*"
                                r"(?P<n>[A-ZÀ-Ý][a-zà-ÿ'’-]{1,14})[ \t]*$", re.M)
RE_TRA_VIRGOLETTE = re.compile(rf"[\"“«]\s?(?P<n>[{_UP}][\w'’-]{{1,20}})\s?[\"”»]")
RE_DETTO = re.compile(rf"(?i:\b(?:dett[oa]|soprannominat[oa]|chiamat[oa]\s+da\s+tutti|per\s+gli\s+amici|per\s+tutti|known\s+as|known\s+locally\s+as|known\s+to\s+[\w ]{{1,40}}?\s+as|aka|a\.k\.a\.|alias|chiamat[oa](?=\s+[\"“«])|chiamat[oa]\s+in\s+famiglia|"
                      rf"nicknamed|goes\s+by|called)\b)[ \t]*[\"“«]?(?P<n>[{_UP}][\w'’-]{{1,20}})")
_PAROLA_MAIUSCOLA_PRIMA = re.compile(rf"(?:[{_UP}][\w'’.-]*|sig\.|sig\.ra|sig\.na|dott\.|dott\.ssa)[ \t]*\(?[ \t]*$", re.I)


def soprannomi(testo: str) -> list[tuple[int, int]]:
    """Soprannomi: «Dave "Dazza" Pritchard», «Mancini Gianluca ("Gianni")», «sig. "Toni" Leone», «detta "Mariagrazia"»."""
    out = []
    for m in RE_TRA_VIRGOLETTE.finditer(testo):
        if _non_nome(m.group("n")) or norm(m.group("n")) in _DE.COMMON_WORDS:
            continue
        pm = re.search(r"([\w'’.-]+)[ \t]*\(?[ \t]*$", testo[max(0, m.start() - 25):m.start()])
        prec = pm.group(1) if pm else ""
        titolo = re.fullmatch(r"(?i)sig\.(?:ra|na)?|dott\.(?:ssa)?|avv\.|mr\.?|mrs\.?|ms\.?|dr\.?|signor[ae]?", prec) is not None
        nome_prima = prec[:1].isupper() and not _non_nome(prec) and norm(prec) not in _DE.COMMON_WORDS
        dm = re.match(rf"[ \t]+([{_UP}][\w'’-]+)", testo[m.end():])
        nome_dopo = dm is not None and not _non_nome(dm.group(1)) and norm(dm.group(1)) not in _DE.COMMON_WORDS
        if titolo or nome_prima or nome_dopo:
            out.append((m.start("n"), m.end("n")))
    for m in RE_DETTO.finditer(testo):
        if not _non_nome(m.group("n")):
            out.append((m.start("n"), m.end("n")))
    for m in RE_SOPRANNOME_PRIMA.finditer(testo):  # «Gigi (Luigi Valle…)», «il Marchino, Marco Serra»
        g = "n" if m.group("n") else "n2"
        w = m.group(g)
        if not _non_nome(w) and norm(w) not in _DE.COMMON_WORDS and norm(w) not in _LESSICO_PRE:
            out.append((m.start(g), m.end(g)))
    for m in RE_NOME_PARENTESI.finditer(testo):  # «del figlio Gennaro (Rino)»
        if norm(m.group("p")) in NOMI and not _non_nome(m.group("n")) and norm(m.group("n")) not in _DE.COMMON_WORDS:
            out.append((m.start("n"), m.end("n")))
    return out


RE_SOPRANNOME_PRIMA = re.compile(rf"(?:(?<![\w])(?P<n>[{_UP}][{_LO}]{{1,12}})[ \t]*\((?=[{_UP}][{_LO}]+[ \t]+[{_UP}][{_LO}]+)|"
                                 rf"(?<![\w])(?:il|la|lo|l['’])[ \t]+(?P<n2>[{_UP}][{_LO}]{{2,12}}),[ \t]+(?=[{_UP}][{_LO}]+[ \t]+[{_UP}][{_LO}]+))")
RE_NOME_PARENTESI = re.compile(rf"(?P<p>[{_UP}][{_LO}]+)[ \t]*\([ \t]*(?P<n>[{_UP}][{_LO}'’-]{{1,15}})[ \t]*\)")


def ruoli(parole: list, genere: str | None = None) -> list[tuple]:
    """Divide le parole di una persona in nomi e cognome. Restituisce [(ruolo, inizio, fine, testo)]."""
    if not parole:
        return []
    tipi = ["nome" if norm(p[2]) in NOMI else "cognome" for p in parole]
    if all(t == "cognome" for t in tipi) and len(parole) == 2 and parole[0][2].isupper() != parole[1][2].isupper():
        tipi = ["cognome", "nome"] if parole[0][2].isupper() else ["nome", "cognome"]  # «KOVALENKO Yuliya»
    elif all(t == "cognome" for t in tipi) and len(parole) >= 2:
        tutte_maiuscole = all(p[2].isupper() for p in parole)
        tipi = (["cognome"] * (len(parole) - 1) + ["nome"]) if tutte_maiuscole else (["nome"] + ["cognome"] * (len(parole) - 1))
    if all(t == "nome" for t in tipi) and len(parole) >= 2:
        # «Rossi Mario» con cognome che è anche un nome (es. «Martino Paolo»): l'ultima parola nota è il nome.
        if parole[0][2].isupper():
            tipi[0] = "cognome"
        else:
            tipi[-1] = "cognome"
    out = []
    # Cognome composto: parole consecutive di tipo cognome diventano un'unica unità.
    i = 0
    while i < len(parole):
        if tipi[i] == "cognome":
            j = i
            while j + 1 < len(parole) and tipi[j + 1] == "cognome":
                j += 1
            out.append(("cognome", parole[i][0], parole[j][1], None))
            i = j + 1
        else:
            out.append(("nome", parole[i][0], parole[i][1], None))
            i += 1
    return out


# ------------------------------------------------------------------ schemi
RE_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+'-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}(?![\w-])")
RE_URL = re.compile(r"\bhttps?://[^\s<>\"')\]]+", re.I)
RE_IBAN = re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?:[ \-]?[A-Z0-9]){11,32}")
RE_CF = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{6}[0-9LMNPQRSTUVlmnpqrstuv]{2}[A-EHLMPR-Ta-ehlmpr-t][0-9LMNPQRSTUVlmnpqrstuv]{2}[A-Za-z][0-9LMNPQRSTUVlmnpqrstuv]{3}[A-Za-z](?![A-Za-z0-9])")
RE_PIVA = re.compile(r"(?<![\w])(?:IT\s?)?\d{11}(?!\d)")
RE_PIVA_CTX = re.compile(r"(?:p\.?\s?iva|partita\s+iva|c\.?f\.?\s*/\s*p\.?\s?iva|vat|codice\s+fiscale)\s*(?:n\.?|n°|:)?\s*(?P<v>(?:IT\s?)?\d{11})(?!\d)", re.I)
RE_CARTA = re.compile(r"(?<![\d\w])[3-6]\d{3}(?:[ \-_]?\d){9,15}(?!\d)")
RE_TEL_INT = re.compile(r"(?<![\w+])(?:\+|00)\s?39[\s.\-/]?\(?(?:3\d{2}|0\d{1,3})\)?(?:[\s.\-/]?\d){5,8}(?!\d)")
RE_TEL_NAZ = re.compile(r"(?<![\w+/.,\-])(?<!\d[ ])(?:3[1-9]\d|0\d{1,3})(?:[ \t]?/[ \t]?|[\s.\-/])?\d(?:[\s.\-/]?\d){5,7}(?!\d|[.,\-]\d|[ ]\d{3,})")
RE_TEL_VERDE = re.compile(r"(?<![\w+/.,\-])(?:800|803|199|840|848|892|895|899)(?:[ .]?|[ \t]?/[ \t]?)\d{3}[ .]?\d{3,4}(?![\d])")
RE_TEL_CTX = re.compile(r"(?:tel(?:efono)?|cell(?:ulare)?|fax|mob(?:ile)?|whatsapp|recapito)\.?\s*(?:n\.?|:)?\s*(?P<v>\+?\d(?:[ .\-/]?\d){5,15})(?![\d])", re.I)
RE_IP = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.]|\.\d)")
_LT = "A-HJ-NPR-TV-Z"
RE_TARGA = re.compile(rf"(?<![A-Z0-9])[{_LT}]{{2}}\s?\d{{3}}\s?[{_LT}]{{2}}(?![A-Z0-9])")
RE_DOC_FORMA = re.compile(r"(?<![A-Z0-9])(?:C[A-Z]\d{5}[A-Z]{2}|A[A-Z]\s?\d{7}|[A-Z]{2}\d{7}|U1[A-Z0-9]{7}[A-Z]|80380\d{15})(?![A-Z0-9])")
RE_DOC_CTX = re.compile(
    r"(?:carta\s+d['’]identit[aà](?:\s+elettronica)?|\bC\.?\s?I\.?E?\.?|documento(?:\s+di\s+(?:riconoscimento|identit[aà]))?|"
    r"passaporto|patente(?:\s+di\s+guida)?|tessera\s+sanitaria|permesso\s+di\s+soggiorno|codice\s+(?:utente|cliente|paziente)|"
    r"badge|matricola|tessera)\s*[:\-]?\s*(?:[A-E][12]?[ \t]+)?(?:n(?:\.|°|umero|r\.?)?\s*)?[:\-]?\s*(?=(?P<v>[A-Z0-9][A-Z0-9]{4,20})(?![A-Za-z0-9]))", re.I)
RE_PRATICA_CTX = re.compile(
    r"(?:pratica|fascicolo|protocollo|prot\.|n\.\s?r\.\s?g\.|r\.\s?g\.(?:\s?n\.\s?r\.)?|rgnr|sinistro|polizza|"
    r"contratto|ordine|fattura|cartella(?:\s+clinica)?|nosologico|ricovero|posizione|ricorso|procedimento|causa|"
    r"verbale|rapporto|denuncia|denunce|segnalazione|ticket|richiesta|rif\.|riferimento|codice\s+pratica|cod\.|preventivo|"
    r"registro|offerta|commessa|ordinativo)(?:[ \t]+(?:inps|inail|asl|clienti|denunce|generale|d'ordine))?[ \t.]*"
    r"(?:n(?:\.|°|umero|r\.?)?\s*)?[:\-]?\s*"
    r"(?=(?P<v>[A-Z0-9][A-Z0-9/\-.]{2,30}[A-Z0-9])(?![A-Za-z0-9]))", re.I)
RE_CATASTO = re.compile(
    r"(?i:(?<![\w])(?:foglio|fg|f\.|particell[ae]|part|p\.lla|mappal[ei]|map|subaltern[oi]|sub|sezione(?:\s+urbana|\s+censuaria)?|sez)\.?)"
    r"[ \t]*(?:n\.?|n°|nr\.?)?[ \t]*[:\-]?[ \t]*(?P<v>\d{1,5}(?:/\d{1,4})?(?![\w/])|[A-Z]{1,2}(?![\w]))")
RE_CATASTO_VICINO = re.compile(r"(?i)\b(?:foglio|fg\.|particell|mappal|subaltern|catast)")
RE_CATASTO_ALTRI = re.compile(r"[ \t]*(?:,|\be\b|-)[ \t]*(?P<v>\d{1,5})(?![\w/])")
RE_CIVICO = re.compile(r"(?P<sep>,?\s*(?:n\.\s?|n°\s?|nr\.?\s?|civ\.?\s?)?)(?P<civ>\d{1,4}(?!\d)(?:\s?/\s?[A-Za-z0-9]{1,3}|[A-Za-z](?![A-Za-z]))?)")
RE_CAP_CITTA = re.compile(rf"(?<![\w\-/])(?P<cap>\d{{5}})[ \t]*[-–]?[ \t]*(?P<citta>[{_UP}][\w'’]+(?:[ \t](?:[{_UP}][\w'’]+|di|del|sul|sull['’]|in|de)){{0,3}})(?:[ \t]*\((?P<prov>[A-Z]{{2}})\))?")
_LUOGO = (rf"[{_UP}][\w'’]+(?:[ \t](?:[{_UP}][\w'’]+|di|del|della|dei|delle|d['’]\w+|in|sul|sull['’]\w+|al|alla|de|"
          rf"sopra|sotto|IN|DI|DEL|DELLA|SUL|AL)){{0,4}}")
_PARTICELLE_LUOGO = {"di", "del", "della", "dei", "delle", "in", "sul", "al", "alla", "de", "sopra", "sotto"}
RE_CITTA_CTX = re.compile(rf"(?<![\w])(?i:nat[oa]\s+a|nat[oa]\s+il\s+[\w./ ]{{4,22}}?\s+a|residente\s+(?:a|in)|domiciliat[oa]\s+(?:a|in)|"
                          rf"con\s+sede\s+(?:legale\s+)?(?:a|in)|sit[oa]\s+in|abitante\s+a|vive\s+a|trasferit[oa]\s+a|comune\s+di|"
                          rf"frazione|fraz\.|localit[aà]['’]?|loc\.|quartiere|rione|borgata)\s+(?P<citta>{_LUOGO})(?:[ \t]*\((?P<prov>[A-Z]{{2}})\))?")
RE_AZIENDA = re.compile(rf"(?P<nome>(?:[{_UP}][\w&'’.-]*[ \t]+){{1,4}}?)(?P<forma>{dati.FORME_SOCIETARIE})(?![\w])")
RE_CAP_ETICHETTA = re.compile(r"(?i:\bc\.?a\.?p\.?)\s*(?:[:.]|(?i:è|e'))?\s*(?P<v>\d{5})(?!\d)")
RE_CARTA_MASCHERATA = re.compile(r"(?<![\d*])\d{4}[ -]?[\d*]{4}[ -]?[\d*]{4}[ -]?[\d*]{3,4}(?![\d*])")
RE_CITTA_SIGLA = re.compile(rf"(?P<citta>[{_UP}][\w'’]+(?:[ \t][{_UP}][\w'’]+){{0,2}})[ \t]*\((?P<prov>[A-Z]{{2}})\)")
RE_CITTA_DATA = re.compile(rf"^[ \t]*(?P<citta>[{_UP}][\w'’]+(?:[ \t][{_UP}][\w'’]+){{0,2}}),[ \t]*(?:l[ìi][ \t]+)?(?:\d{{1,2}}[ \t]+[a-z]+[ \t]+\d{{4}}|\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{2,4}})", re.M)
RE_CITTA_ETICHETTA = re.compile(rf"(?i:luogo\s+di\s+nascita|comune\s+di\s+(?:nascita|residenza)|citt[aà]\s+di\s+(?:nascita|residenza)|residenza|domicilio|citt[aà]|comune|localit[aà]|sede|residente|ubicazione(?:\s+del\s+rischio)?)[ \t]*:[ \t]*(?P<citta>{_LUOGO})")
RE_CITTA_PRIMA_VIA = re.compile(rf"(?P<citta>{_LUOGO})[ \t]*,[ \t]*(?=(?i:via|viale|piazza|piazzale|corso|largo|vicolo|strada|localit[aà]|loc\.|frazione|fraz\.|quartiere)\b)")


def taglia_luogo(s: str) -> str:
    parole = s.split()
    while parole and (parole[-1].lower() in _PARTICELLE_LUOGO or re.fullmatch(r"(?i)d['’]|sull['’]", parole[-1])
                      or (len(parole) > 1 and norm(parole[-1]) in dati.NON_NOMI)):
        parole.pop()
    return " ".join(parole)
RE_CODICE_BARRA = re.compile(r"(?<![\w/.-])[A-Z0-9]{1,8}(?:[/-][A-Z0-9]{1,10}){1,3}(?![\w/-])")
RE_NORMATIVA_VICINA = re.compile(r"(?i)(?<![\w])(?:legge|l\.|d\.?\s?lgs|d\.?\s?p\.?\s?r|d\.?\s?l\.|art\.|reg\.|regolamento|direttiva|dpcm|circolare)\.?\s*(?:\(?ue\)?\s*)?(?:n\.?\s*)?$")
RE_NUMERO_LUNGO = re.compile(r"(?<![\w.,/])\d{6,}(?![\w,]|\.\d)")
RE_PATOLOGIE = re.compile(r"(?<![\w])(?:" + "|".join(re.escape(p) for p in sorted(dati.PATOLOGIE, key=len, reverse=True)) + r")(?![\w])", re.I)
_VIA = "|".join(re.escape(p) for p in sorted(dati.PREFISSI_STRADA, key=len, reverse=True))
RE_VIA = re.compile(rf"(?<![\w])(?P<pref>(?i:{_VIA}))(?![\w])[ \t]+")
_PAROLA_VIA = re.compile(rf"(?:dei|dai|d[ei]|del|dell[aoe]|dell['’]|degli|della|dello|d['’]|delle|al|alla|San|Santa|Sant['’]|S\.|[IVXL]+|\d{{1,2}}|[{_UP}][\w'’.-]*)(?![\w])")


def _cifre(s: str) -> str:
    return re.sub(r"\D", "", s)


def trova_schemi(testo: str, modalita: str = "bilanciata", sanitari: bool = True) -> list[Span]:
    spans: list[Span] = []
    add = spans.append
    for m in RE_URL.finditer(testo):
        add(Span(m.start(), m.end(), "URL", m.group(0)))
    for m in RE_EMAIL.finditer(testo):
        add(Span(m.start(), m.end(), "EMAIL", m.group(0)))
    for m in RE_IBAN.finditer(testo):
        grezzo = m.group(0)
        paese = grezzo[:2]
        lung = V.LUNGHEZZE_IBAN.get(paese)
        if not lung:
            continue
        # Taglia esattamente alla lunghezza del paese (le parole maiuscole dopo l'IBAN non vanno incluse).
        n, fine = 0, m.start()
        for k, ch in enumerate(grezzo):
            if ch.isalnum():
                n += 1
                if n == lung:
                    fine = m.start() + k + 1
                    break
        if n < lung:
            continue
        val = testo[m.start():fine]
        conf = 1.0 if V.iban_valido(val) else 0.8
        add(Span(m.start(), fine, "IBAN", val, conf))
    for m in RE_CF.finditer(testo):
        val = m.group(0)
        if not val.isupper() and not V.cf_valido(val):
            continue
        add(Span(m.start(), m.end(), "CF", val, 1.0 if V.cf_valido(val) else 0.8))
    for m in RE_PIVA_CTX.finditer(testo):
        add(Span(m.start("v"), m.end("v"), "PIVA", m.group("v"), 1.0))
    for m in RE_PIVA.finditer(testo):
        if V.piva_valida(m.group(0)):
            add(Span(m.start(), m.end(), "PIVA", m.group(0), 0.9))
    for m in RE_CARTA.finditer(testo):
        if V.luhn_valido(m.group(0)) and 13 <= len(_cifre(m.group(0))) <= 19:
            add(Span(m.start(), m.end(), "CARTA", m.group(0), 0.9))
    for rx in (RE_TEL_INT, RE_TEL_NAZ):
        for m in rx.finditer(testo):
            c = _cifre(m.group(0))
            if 8 <= len(c) <= 13:
                add(Span(m.start(), m.end(), "TELEFONO", m.group(0), 0.9))
    for m in RE_TEL_VERDE.finditer(testo):
        add(Span(m.start(), m.end(), "TELEFONO", m.group(0), 0.85))
    for m in RE_TEL_CTX.finditer(testo):
        if 6 <= len(_cifre(m.group("v"))) <= 13:
            add(Span(m.start("v"), m.end("v"), "TELEFONO", m.group("v"), 0.95))
    for m in RE_IP.finditer(testo):
        add(Span(m.start(), m.end(), "IP", m.group(0)))
    for m in RE_TARGA.finditer(testo):
        add(Span(m.start(), m.end(), "TARGA", m.group(0), 0.8))
    for m in RE_DOC_FORMA.finditer(testo):
        add(Span(m.start(), m.end(), "DOCUMENTO", m.group(0), 0.85))
    for m in RE_DOC_CTX.finditer(testo):
        v = m.group("v")
        if sum(ch.isdigit() for ch in v) >= 2:
            add(Span(m.start("v"), m.end("v"), "DOCUMENTO", v, 0.95))
    for m in RE_PRATICA_CTX.finditer(testo):
        v = m.group("v").rstrip(".-/")
        if re.fullmatch(r"(?:19|20)\d\d|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", v):
            continue  # un anno o una data non sono un numero di pratica («ordine 2025», «verbale 10/10/2025»)
        if sum(ch.isdigit() for ch in v) >= 2:
            add(Span(m.start("v"), m.start("v") + len(v), "PRATICA", v, 0.9))
    for m in RE_CATASTO.finditer(testo):
        if not m.group("v")[0].isdigit():  # «sezione B» solo vicino a foglio e particella (non «SEZIONE A - DATI…»)
            vicino = testo[max(0, m.start() - 80):m.end() + 80]
            if (not RE_CATASTO_VICINO.search(vicino) or re.match(r"[ \t]*[-–]", testo[m.end():])
                    or (m.group(0).split()[0].isupper() and len(m.group(0).split()[0]) > 3)):
                continue
        add(Span(m.start("v"), m.end("v"), "CATASTO", m.group("v"), 0.9))
        fine = m.end()
        while True:  # «particelle 48, 49 e 50»
            a = RE_CATASTO_ALTRI.match(testo, fine)
            if not a or not m.group("v").isdigit():
                break
            add(Span(a.start("v"), a.end("v"), "CATASTO", a.group("v"), 0.85))
            fine = a.end()
    for m in RE_CAP_CITTA.finditer(testo):
        citta = m.group("citta")
        # tronca alle parole che sono davvero il comune (es. «00185 Roma Tel.» → «Roma»)
        parole = citta.split()
        while parole and norm(parole[-1]) in dati.NON_NOMI:
            parole.pop()
        if not parole:
            continue
        citta = " ".join(parole)
        fine = m.start("citta") + len(citta)
        if m.group("prov") and m.end("citta") == m.start("citta") + len(m.group("citta")):
            if len(citta) == len(m.group("citta")):
                fine = m.end()
        add(Span(m.start(), fine, "CAP_CITTA", testo[m.start():fine], 0.95, {"citta": citta}))
    for m in RE_CITTA_CTX.finditer(testo):
        c = taglia_luogo(m.group("citta"))
        if not c or (norm(c.split()[0]) in dati.NON_NOMI and norm(c) not in COMUNI):
            continue
        fine = m.end() if m.group("prov") and c == m.group("citta") else m.start("citta") + len(c)
        add(Span(m.start("citta"), fine, "CITTA", testo[m.start("citta"):fine], 0.9))
    for m in RE_CITTA_PRIMA_VIA.finditer(testo):  # «Sede: Piacenza, via Emilia 97»
        parole = m.group("citta").split()
        while parole and _non_nome(parole[0]) and norm(" ".join(parole)) not in COMUNI:
            parole.pop(0)
        c = taglia_luogo(" ".join(parole))
        if c:
            a = m.start("citta") + m.group("citta").find(c)
            add(Span(a, a + len(c), "CITTA", c, 0.85))
    for m in RE_CARTA_MASCHERATA.finditer(testo):
        if "*" in m.group(0):
            add(Span(m.start(), m.end(), "DOCUMENTO", m.group(0), 0.9))  # carta letta in parte: «5412 75** **** 3390»
    for m in RE_CAP_ETICHETTA.finditer(testo):
        add(Span(m.start("v"), m.end("v"), "CAP", m.group("v"), 0.95))
    for m in RE_CITTA_SIGLA.finditer(testo):
        parole = m.group("citta").split()
        while parole and _non_nome(parole[0]) and norm(parole[0]) not in COMUNI:
            parole.pop(0)
        if parole and m.group("prov") in dati.SIGLE_PROVINCE:
            c = " ".join(parole)
            a = m.end("citta") - len(c)
            add(Span(a, m.end(), "CITTA", testo[a:m.end()], 0.85))
    for m in RE_CITTA_ETICHETTA.finditer(testo):
        c = taglia_luogo(m.group("citta"))
        if c and not (norm(c.split()[0]) in dati.NON_NOMI and norm(c) not in COMUNI):
            add(Span(m.start("citta"), m.start("citta") + len(c), "CITTA", c, 0.85))
    for m in RE_CITTA_DATA.finditer(testo):
        if not _non_nome(m.group("citta").split()[0]) or norm(m.group("citta")) in COMUNI:
            add(Span(m.start("citta"), m.end("citta"), "CITTA", m.group("citta"), 0.85))
    if modalita == "fuga":
        for m in RE_CODICE_BARRA.finditer(testo):
            if sum(ch.isdigit() for ch in m.group(0)) >= 4 and not RE_NORMATIVA_VICINA.search(testo[max(0, m.start() - 30):m.start()]):
                add(Span(m.start(), m.end(), "PRATICA", m.group(0), 0.5))
    spans.extend(trova_codici(testo))
    spans.extend(luoghi_it(testo))
    spans.extend(trova_indirizzi(testo))
    if sanitari:
        for m in RE_PATOLOGIE.finditer(testo):
            add(Span(m.start(), m.end(), "SANITARIO", m.group(0), 0.9))
    if modalita == "fuga":
        for m in RE_NUMERO_LUNGO.finditer(testo):
            add(Span(m.start(), m.end(), "NUMERO", m.group(0), 0.5))
    return spans


# Codici generici (identificativi senza un formato noto): token con cifre e lettere o separatori, numeri lunghi,
# numeri dopo «n.», «no.», «#». Priorità bassa (CODICE): date, telefoni, indirizzi e schemi noti vincono sempre.
RE_TOKEN_CODICE = re.compile(r"(?<![\w.,/\-])(?=[A-Za-z0-9\-/]*\d)[A-Za-z0-9]+(?:[\-/][A-Za-z0-9]+){0,6}(?![\w/\-]|[.,]\d)")
RE_GRUPPI_4 = re.compile(r"(?<![\w])\d{4}(?:[ ]\d{4}){2,5}(?![\w])")
RE_NUMERO_DOPO_ETICHETTA = re.compile(r"(?i:(?<![\w])(?:n\.|n°|nr\.|no\.|num\.|#|rep\.|racc\.|cron\.|mat\.?|pos\.)|\bnumber\b|\bnumero\b|\bmatricola(?:\s+[a-zà-ù]+)?|\buser\s+id|\bid)"
                                      r"[ \t]*:?[ \t]*(?P<v>(?:[A-Z]{1,4}[ ](?=\d{4}/\d))?(?:\d{1,3}(?:\.\d{3})+|\d{2,8}(?:[ ]\d{2,8}){1,4}|\d{3,12}(?:/\d{2,4})?))(?![\w]|[.,]\d)")
RE_NORMATIVA_EN = re.compile(r"(?i)(?:section|sec\.|§|u\.?s\.?c\.?|c\.?f\.?r\.?|act|chapter|rule|title|artt?\.|articol[oi]|comma|c\.c\.|c\.p\.c?\.|"
                             r"delibera(?:zione)?|determina|direttiva)\s*(?:n\.?\s*|no\.?\s*)?$")
RE_ANNI = re.compile(r"(?:19|20)\d\d[\-/](?:(?:19|20)?\d\d)")


def _codice_plausibile(v: str) -> bool:
    cifre = sum(c.isdigit() for c in v)
    lettere = sum(c.isalpha() for c in v)
    sep = sum(c in "-/" for c in v)
    if (RE_ANNI.fullmatch(v) or re.fullmatch(r"\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?", v)
            or re.fullmatch(r"(?:19|20)\d\d[/\-]\d{1,2}[/\-]\d{1,2}", v)):
        return False  # «2019-2024», «2024/25», date
    if lettere and not cifre >= 3:
        return False
    if lettere and re.fullmatch(r"[A-Za-z]{1,3}\d{1,2}|[A-Z]\d{3}", v):
        return False  # «A4», «F24», «H24», «B2B»; «H945» è il codice catastale di un comune
    if re.search(r"(?i)-(?:bis|ter|quater|quinquies|sexies|septies|octies)$", v):
        return False  # «412-ter»: articolo di legge
    if lettere and lettere > 3 * cifre and not sep:
        return False  # parole con un numero dentro
    if re.fullmatch(r"[a-z]+-?\d{1,3}", v):
        return False  # «covid-19», «mp3»
    if not lettere and not sep:
        return cifre >= 7
    if not lettere:
        if sep == 1 and "/" in v:  # «1000/1000» (millesimi), «4012/2915»: solo «n. 482/2025»
            return re.fullmatch(r"\d{1,6}/(?:19|20)\d\d", v) is not None
        return cifre >= 5 and (sep >= 2 or cifre >= 7)
    return cifre >= 3


def trova_codici(testo: str) -> list[Span]:
    out = []
    for m in RE_TOKEN_CODICE.finditer(testo):
        v = m.group(0)
        if not _codice_plausibile(v):
            continue
        prima = testo[max(0, m.start() - 30):m.start()]
        if RE_NORMATIVA_VICINA.search(prima) or RE_NORMATIVA_EN.search(prima):
            continue
        if re.fullmatch(r"\d{1,6}/(?:19|20)\d\d", v) and not re.search(r"(?i)(?:n\.|n°|nr\.|no\.|#|numero|number|prot|rif|r\.g|rep|pratica|ricorso|causa)[^\n]{0,12}$", prima):
            continue  # «482/2025» da solo può essere altro; con «n.» o «prot.» è un numero di pratica
        anno = re.search(r"(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])", v) and re.search(r"[/-]", v)
        out.append(Span(m.start(), m.end(), "PRATICA" if anno else "CODICE", v, 0.7))  # con un anno: si sposta come le date
    for m in RE_GRUPPI_4.finditer(testo):
        out.append(Span(m.start(), m.end(), "CODICE", m.group(0), 0.7))
    for m in RE_NUMERO_DOPO_ETICHETTA.finditer(testo):
        prima = testo[max(0, m.start() - 30):m.start()]
        if RE_NORMATIVA_VICINA.search(prima) or RE_NORMATIVA_EN.search(prima):
            continue
        out.append(Span(m.start("v"), m.end("v"), "CODICE", m.group("v"), 0.7))
    return out


RE_SEQ_LUOGO_IT = re.compile(rf"(?<![\w'’-])[{_UP}][\w'’.-]*(?:[ \t](?:[{_UP}][\w'’.-]*|(?:della|delle|dei|del|di|d['’]\w+|in|sull['’]\w+|sul|alla|al|de|sopra|sotto|ne['’]|"
                             rf"DELLA|DEL|DI|IN|SUL|AL)(?![\w'’])))*")
RE_CONTESTO_LOCALITA = re.compile(r"(?i)(?:\bCOMUNE\s+DI|\b(?-i:DI|DA|IN|A)|\bfrazione(?:\s+di)?|\bfraz\.|\blocalit[àa]|\bloc\.|\bborgo|\bcontrada|\bc\.da|"
                                  r"\bnat[oaie]\s+(?:a|in)|\bresident[ei]\s+(?:a|in)|\bdomiciliat[oaie]\s+(?:a|in)|\babita(?:nte)?\s+a|"
                                  r"\bcomune\s+di|\bpaese\s+di|\bvive\s+a|\bsit[oa]\s+in|\d{5}[ \t]+)\s*$")
RE_SIGLA_DOPO = re.compile(r"[ \t]*\((?:A[GLNOPQRT]|B[AGILNORSTZ]|C[AEHILNORSZT]|E[N]|F[CEGIMORU]|G[EOR]|I[MS]|K[R]|L[CEIOTU]|"
                           r"M[BCEIN-OST]|N[AOU]|O[GLRT]|P[ACDEGIN-OR-VZ]|R[AC-EGIMNOV]|S[AIOPRSUV]|T[AEOPNRS]|U[D]|V[ABCEIRTV])\)")
RE_PREP_LUOGO_IT = re.compile(r"(?i)\b(?:a|ad|di|da|in|presso|verso|per|tra|fra|nel|nei|comune|frazione|località|loc\.)\s+$")


def luoghi_it(testo: str) -> list[Span]:
    """Comuni, frazioni, quartieri e città straniere del dizionario. Più parole bastano da sole; una parola sola vale
    se non è ambigua (parola comune, nome o cognome), altrimenti serve una preposizione davanti («a Bra», «di Massa»)."""
    out = []
    for m in RE_SEQ_LUOGO_IT.finditer(testo):
        pos = [(x.start() + m.start(), x.end() + m.start()) for x in re.finditer(r"\S+", m.group(0))]
        i = 0
        while i < len(pos):
            preso = 0
            for k in range(min(6, len(pos) - i), 0, -1):
                a, b = pos[i][0], pos[i + k - 1][1]
                cand = testo[a:b].rstrip(".,")
                n = norm(cand)
                ufficiale = n not in dati.LUOGHI_IT and (n in dati.COMUNI_UFF or n in dati.LOCALITA_UFF)
                if (n not in dati.LUOGHI_IT and not ufficiale) or re.split(r"['’]", _precedente(testo, a))[-1] in _LUOGHI_INTITOLATI:
                    continue  # «ospedale Santa Maria Nuova», «via Roma»: non sono il comune
                if ufficiale and (not cand[:1].isupper() or (k == 1 and ((cand.isupper() and n not in dati.COMUNI_UFF) or n in dati._GREZZE_IT or n in _LESSICO_PRE
                                                                          or n in _PAROLE_COMUNI or n in dati.NON_NOMI or len(n) < 4))):
                    continue  # «del», «Tel», «Club», «Polizza»: parole, non località
                if ufficiale:  # elenchi ISTAT: solo con un contesto di luogo
                    forte = RE_CONTESTO_LOCALITA.search(testo[max(0, a - 30):a]) or RE_SIGLA_DOPO.match(testo, a + len(cand))
                    debole = n in dati.COMUNI_UFF and RE_PREP_LUOGO_IT.search(testo[max(0, a - 12):a]) and not (
                        k == 1 and (n in _LESSICO_PRE or n in _PAROLE_COMUNI or n in dati.NON_NOMI or n in NOMI_BASE or len(n) < 4))
                    if not (forte or debole):
                        continue
                    out.append(Span(a, a + len(cand), "CITTA", cand, 0.7))
                    preso = k
                    break
                if k == 1:
                    ambiguo = (n in dati.AMBIGUI_LUOGHI_IT or n in dati.NON_NOMI or n in NOMI_BASE or n in COGNOMI_BASE
                               or len(n) < 4 or n in _LESSICO_PRE)
                    if ambiguo and not RE_PREP_LUOGO_IT.search(testo[max(0, a - 12):a]):
                        continue
                out.append(Span(a, a + len(cand), "CITTA", cand, 0.75))
                cap = re.match(r"[ \t]*,?[ \t]*\(?(\d{5})(?![\d/.,]\d|\d)", testo[a + len(cand):])  # «Treviso 31100», «Carpi (41012)»
                if cap:
                    x = a + len(cand) + cap.start(1)
                    out.append(Span(x, x + 5, "CAP", cap.group(1), 0.85))
                preso = k
                break
            i += preso or 1
    return out


_NON_VIA = {"pec", "email", "e-mail", "mail", "posta", "fax", "telefono", "web", "internet", "sms", "whatsapp", "raccomandata",
            "corriere", "app", "telematica", "portale", "sito", "piattaforma", "bonifico", "skype", "zoom", "teams"}


RE_VIA_SENZA_PREFISSO = re.compile(
    rf"(?<![\w'’.-])(?P<via>(?:(?:Don|San|Santa|Sant['’]|S\.|de|del|della|dei|delle|degli|di)[ \t]+|dell['’])?[{_UP}][\w'’]+(?:[ \t][{_UP}][\w'’]+){{0,2}})"
    rf"[ \t]+(?P<civ>\d{{1,4}}(?:[ \t]?/[ \t]?[A-Za-z0-9]{{1,3}}|[A-Za-z](?![\w]))?)[ \t]*(?:,|-|–)[ \t]*"
    rf"(?=\d{{5}}(?!\d)|(?:interno|int\.|scala|piano|frazione|fraz\.|località|loc\.)\b|(?P<c>[{_UP}][\w'’]+(?:[ \t][{_UP}][\w'’]+){{0,2}}))")


_VIA_NUDA = (rf"(?P<via>(?:dell['’]|(?:della|dei|degli|delle|del|Don|San|Santa)[ \t]+|Sant['’])?[{_UP}][\w'’]+(?:[ \t](?:[{_UP}][\w'’]+|da|di|de|del|della)){{0,3}})"
             rf"[ \t]+(?P<civ>\d{{1,4}}(?:[ \t]?/[ \t]?[A-Za-z0-9]{{1,3}}|[A-Za-z](?![\w]))?)(?![\w]|[.,/]\d)")
RE_VIA_DOPO_CITTA = re.compile(rf"(?<![\w'’])(?P<citta>[{_UP}][\w'’]+(?:[ \t][{_UP}][\w'’]+){{0,2}}),[ \t]+(?:\d{{5}},[ \t]+)?"
                               rf"(?:(?:località|loc\.|frazione|fraz\.)[ \t]+[{_UP}][\w'’]*(?:[ \t][{_UP}][\w'’]*){{0,2}},[ \t]+)?" + _VIA_NUDA)
RE_VIA_DOPO_INDIZIO = re.compile(r"(?i:residen\w*|domicilio(?:[ \t]+fiscale)?|indirizzo|abitazione|alloggio|appartamento|"
                                 r"magazzino(?:[ \t]+e[ \t]+uffici)?|uffici|sede(?:[ \t]+legale|[ \t]+operativa)?)"
                                 r"[ \t]*(?::|[ \t](?:in|di|a|al|nel)|)[ \t]*(?:\.{2,}[ \t]*)?" + _VIA_NUDA)


def trova_indirizzi(testo: str) -> list[Span]:
    out = []
    for m in RE_VIA_SENZA_PREFISSO.finditer(testo):
        via = m.group("via")
        primo = via.split()[0]
        if _non_nome(primo) and norm(primo) not in ("don", "san", "santa"):
            continue
        if norm(via) in dati.LUOGHI_IT or norm(primo) in _LESSICO_PRE:
            continue  # «Verona 12, …» è una città; «Pagina 3, …» no
        if m.group("c") is not None and norm(m.group("c")) not in dati.LUOGHI_IT:
            continue
        meta = {"via": via, "pref": "", "via_inizio": m.start("via"), "via_fine": m.end("via"),
                "civ": m.group("civ"), "civ_inizio": m.start("civ"), "civ_fine": m.end("civ")}
        out.append(Span(m.start("via"), m.end("civ"), "INDIRIZZO", testo[m.start("via"):m.end("civ")], 0.85, meta))
    for m in RE_VIA.finditer(testo):
        pref = m.group("pref")
        if pref[0].islower() and not re.match(rf"(?:(?:dei|del|della|delle|degli|dello|dell['’]|di|d['’]|al|alla|ai|agli|alle)[ \t]*)?[{_UP}0-9]",
                                              testo[m.end():m.end() + 12]):
            continue  # «via email»; ma «via dei Mille», «via del Mare» sì
        i = m.end()
        parole = []
        while len(parole) < 6:
            pm = _PAROLA_VIA.match(testo, i)
            if not pm:
                break
            w = pm.group(0)
            if w.isdigit() and parole:
                break  # è il civico
            parole.append((pm.start(), pm.end(), w))
            if w[-1] in "'’":  # «dell'Industria»: la parola dopo l'apostrofo è attaccata
                i = pm.end()
                continue
            sp = re.match(r"[ \t]", testo[pm.end():pm.end() + 1])
            if not sp:
                break
            i = pm.end() + 1
        while parole and re.fullmatch(r"dei|dai|d[ei]|del|dell[aoe]|degli|della|dello|delle|al|alla", parole[-1][2]):
            parole.pop()
        if not parole or not any(p[2][0].isupper() or p[2][0].isdigit() for p in parole):
            continue
        civico_dopo = RE_CIVICO.match(testo, parole[-1][1])
        if pref[0].islower() and (parole[0][2].isupper() and len(parole[0][2]) <= 4 and not re.fullmatch(r"[IVXL]+", parole[0][2])
                                  or norm(parole[0][2]) in _NON_VIA
                                  or (_non_nome(parole[0][2]) and not (civico_dopo and civico_dopo.group("civ"))
                                      and norm(parole[0][2]) not in COMUNI)):
            continue  # «via PEC», «via Email»: non è un indirizzo; «via Roma 15», «via dei Tigli 3» sì
        nome_ini, nome_fine = parole[0][0], parole[-1][1]
        fine = nome_fine
        civ = RE_CIVICO.match(testo, nome_fine)
        meta = {"via": testo[nome_ini:nome_fine], "pref": pref, "via_inizio": nome_ini, "via_fine": nome_fine}
        if civ and civ.group("civ"):
            fine = civ.end()
            meta.update(civ=civ.group("civ"), civ_inizio=civ.start("civ"), civ_fine=civ.end("civ"))
        out.append(Span(m.start(), fine, "INDIRIZZO", testo[m.start():fine], 0.95, meta))
        dopo = re.match(rf"[ \t]*(?:[,–-]|\ba\b|\bin\b)[ \t]*(?P<c>{_LUOGO})", testo[fine:])
        if dopo:
            c = taglia_luogo(dopo.group("c"))
            if c and (not _non_nome(c.split()[0]) or norm(c) in COMUNI):
                a = fine + dopo.start("c")
                out.append(Span(a, a + len(c), "CITTA", c, 0.9))
        cap = re.match(r"[^\n]{0,25}?(?<![\d.,])(?P<cap>\d{5})(?![\d.,]\d|\d)", testo[fine:])  # «…112, 59100», «… (43036)», «…, interno 7, 10153»
        if cap:
            out.append(Span(fine + cap.start("cap"), fine + cap.end("cap"), "CAP", cap.group("cap"), 0.9))
    # Vie senza «via» dopo una città o dopo un indizio di indirizzo: «Parma, Bixio 18», «residente in Bari, 70125,
    # Re David 220», «Domicilio fiscale: Madonna Pellegrina 40», «con sede in dell'Industria 27»
    for rx in (RE_VIA_DOPO_CITTA, RE_VIA_DOPO_INDIZIO):
        for m in rx.finditer(testo):
            via = m.group("via")
            parole = re.findall(r"[\w]+", via)
            nucleo = [w for w in parole if norm(w) not in ("dell", "della", "dei", "degli", "delle", "del", "di", "don", "san", "santa", "sant")]
            if rx is RE_VIA_DOPO_CITTA and (not nucleo or all(_non_nome(w) and norm(w) not in COGNOMI and norm(w) not in NOMI for w in nucleo)):
                if not re.match(r"(?i)dell['’]|della|dei|degli|delle|del\b", via):
                    continue
            if rx is RE_VIA_DOPO_CITTA and norm(taglia_luogo(m.group("citta")) or "") not in dati.LUOGHI_IT:
                continue
            if norm(via) in dati.LUOGHI_IT and rx is RE_VIA_DOPO_INDIZIO:
                continue
            meta = {"via": via, "pref": "", "via_inizio": m.start("via"), "via_fine": m.end("via"),
                    "civ": m.group("civ"), "civ_inizio": m.start("civ"), "civ_fine": m.end("civ")}
            out.append(Span(m.start("via"), m.end("civ"), "INDIRIZZO", testo[m.start("via"):m.end("civ")], 0.85, meta))
    # CAP subito dopo un indirizzo senza «via»: «Bixio 18, interno 4, 43125»
    for s in list(out):
        if s.tipo == "INDIRIZZO" and s.meta.get("pref") == "":
            cap = re.match(r"[^\n]{0,30}?(?<![\d.,])(?P<cap>\d{5})(?![\d.,]\d|\d)", testo[s.fine:])
            if cap and not re.search(r"(?i)tel|cell|fax|n\.|nr", cap.group(0)):
                out.append(Span(s.fine + cap.start("cap"), s.fine + cap.end("cap"), "CAP", cap.group("cap"), 0.9))
    return out


def trova_aziende(testo: str) -> list[Span]:
    out = []
    for m in RE_AZIENDA.finditer(testo):
        nome = m.group("nome").strip()
        parole = nome.split()
        while parole and norm(parole[0]) in dati.NON_NOMI:
            parole.pop(0)
        if not parole:
            continue
        nome = " ".join(parole)
        inizio = m.start("nome") + m.group("nome").find(nome)
        out.append(Span(inizio, m.end(), "AZIENDA", testo[inizio:m.end()], 0.9,
                        {"nome": nome, "forma": m.group("forma"), "nome_fine": inizio + len(nome)}))
    return out


def arbitra(spans: list[Span]) -> list[Span]:
    """Sceglie intervalli senza sovrapposizioni: vince la priorità del tipo, poi la lunghezza."""
    ordinati = sorted(spans, key=lambda s: (-PRIORITA.get(s.tipo, 0), -(s.fine - s.inizio), s.inizio))
    scelti: list[Span] = []
    occupati = Intervalli()
    for s in ordinati:
        if occupati.libero(s.inizio, s.fine):
            occupati.aggiungi(s.inizio, s.fine)
            scelti.append(s)
    return sorted(scelti, key=lambda s: s.inizio)
