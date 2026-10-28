"""Cuore dello scudo: la sessione tiene la mappa reale ↔ finto, pseudonimizza e ripristina.

Principi:
- coerenza: la mappa vale per tutta la sessione (più documenti, più turni di chat);
- nomi a livello di parola: ogni nome di battesimo e ogni cognome ha il suo alias, così «Mario Rossi»,
  «Rossi», «M. Rossi», «ROSSI MARIO» e «Anna Rossi» (stessa famiglia) restano coerenti da soli;
- schemi con controllo: i finti hanno caratteri di controllo validi e lo stesso formato;
- date: spostamento costante (vedi date.py);
- ripristino prudente: ciò che non è certo si segnala, non si indovina.
"""
from __future__ import annotations

import datetime as dt
import logging
import random
import re
import secrets
from dataclasses import asdict, dataclass, field

from . import dati, generatori as G, validatori as V
from . import dati_en as DE
from . import inglese as EN
from . import prefiltro as PF
from . import riconoscitori as R
from .dati import norm
from .intervalli import Intervalli
from .date import DataTrovata, convenzione_date, formato_lungo, scegli_delta, sposta, trova_date

log = logging.getLogger("sosia")

_NOMI_STATI = "|".join(sorted(DE.US_STATES.values(), key=len, reverse=True)).replace("{", "{{").replace("}", "}}")
TIPI_EN = ("SSN", "ITIN", "NINO", "NHS", "ROUTING", "SORTCODE", "CONTO", "PASSAPORTO", "PATENTE", "VIN", "CATASTO")
TIPI_SCHEMA = ("CF", "IBAN", "PIVA", "CARTA", "TELEFONO", "IP", "TARGA", "DOCUMENTO", "CODICE", "PRATICA", "NUMERO", "CAP") + TIPI_EN
_CIFRE = {"PIVA", "CARTA", "NUMERO", "SSN", "ITIN", "NHS", "ROUTING", "SORTCODE"}
_FONTI_EN = {"title", "cue", "label", "last-first", "dictionary", "first-name", "surname"}
_SANTI = {"san", "santa", "santo", "sant'", "s.", "ss.", "beata", "beato", "madonna"}


ISTRUZIONI_MARCATORI = (
    "Non conosci la data di oggi e non devi indovinarla. Quando una risposta dipende da oggi, scrivi un marcatore "
    "che verrà calcolato sul computer dell'utente: ⟦OGGI⟧ per la data di oggi; ⟦ETA:gg/mm/aaaa⟧ per l'età di chi è "
    "nato in quella data; ⟦GIORNI:gg/mm/aaaa⟧ per quanto manca a quella data o quanto tempo è passato; "
    "⟦SCADENZA:gg/mm/aaaa⟧ per dire se un termine è scaduto. Usa le date come compaiono nel documento. "
    "Le annotazioni [età N anni] o [age N] nel documento sono già calcolate rispetto a oggi.")
RE_MARCATORE = re.compile(r"⟦\s*(?P<tipo>OGGI|ETA|ETÀ|GIORNI|SCADENZA)\s*(?::\s*(?P<arg>[^⟧]{1,40}))?⟧", re.I)
RE_SEGNAPOSTO = re.compile(r"⟦S\d+⟧")
RE_ANNOTAZIONE_ETA = re.compile(r" ?\[(?:età \d{1,3} ann[oi]|age \d{1,3})\]")
RE_CONTESTO_NASCITA = re.compile(r"(?i)\b(?:nat[oa]|nascita|classe|born|birth|dob|d\.o\.b\.?|birthday|birthdate)\b[^\n]{0,30}$")


class FugaRilevata(RuntimeError):
    """Dopo la sostituzione è rimasto un dato originale: il testo non va inviato."""


class SessioneScaduta(RuntimeError):
    pass


@dataclass
class Configurazione:
    modalita: str = "bilanciata"          # «bilanciata» oppure «fuga» (sostituisce di più nel dubbio)
    aziende: bool = False                 # sostituire le ragioni sociali (S.r.l., S.p.A.…)
    citta: bool = True
    date: bool | str = True               # True/«tutte»; «nascita» = solo date di nascita (agenti con date vere); False
    anni_contesto: bool = True            # «nel 2019», «anno 2020»
    conserva_settimana: bool = True       # Δ multiplo di 7
    settimane_min: int = 26
    settimane_max: int = 156
    iban_banca: str = "casuale"           # «casuale» o «mantieni» (stesso ABI)
    sanitari: str = "segnala"             # «segnala», «sostituisci», «lascia»
    scadenza_ore: int = 168
    margine_anni_ripristino: int = 2
    blocca_fughe: bool = True             # in modalità fuga: errore se resta un dato originale
    fuga_sensibili: bool = False          # True: testi sanitari e legali «a prova di fuga» in automatico (senza errore)
    seme: int | None = None               # solo per prove riproducibili
    dichiara_oggi: bool = False           # True: dice al modello la «data di oggi» spostata (Δ ricavabile dal fornitore)
    ner_modo: str = "pieno"               # «pieno»: modello su tutto il testo; «auto»: solo dove servono (proxy)
    eta_locale: bool = True               # accanto alle date di nascita: «⟦età N anni⟧» calcolata sul PC


@dataclass
class Esito:
    testo: str
    sostituzioni: list = field(default_factory=list)   # (inizio, fine, nuovo, tipo) nelle coordinate del testo d'ingresso
    conteggi: dict = field(default_factory=dict)
    avvisi: list = field(default_factory=list)
    incerti: list = field(default_factory=list)        # [{"testo", "inizio", "fine", "motivo"}]
    # Solo in memoria, per il banco di prova: (tipo, originale, nuovo). Non va mai scritto nei registri.
    dettagli: list = field(default_factory=list, repr=False)


def _caso_parola(campione: str, parola: str) -> str:
    lettere = [c for c in campione if c.isalpha()]
    if len(lettere) > 1 and all(c.isupper() for c in lettere):
        return parola.upper()
    if lettere and all(c.islower() for c in lettere):
        return parola.lower()
    if lettere and lettere[0].isupper() and parola[:1].islower():
        return parola[:1].upper() + parola[1:]
    return parola


def _anni_compiuti(nascita: dt.date, oggi: dt.date) -> int:
    return oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))


_PARTICELLE_MINUSCOLE = {"al", "alla", "di", "del", "della", "dei", "delle", "in", "sul", "sulla", "de", "da", "e", "of",
                         "the", "upon", "on", "le", "la"}


def applica_caso(campione: str, parola: str, per_parola: bool = False) -> str:
    """Trasferisce maiuscole e minuscole; per i nomi, parola per parola se il numero di parole coincide («di Bergamo»)."""
    if parola.isupper() and len(parola) > 1 and campione[:1].isupper() and any(c.islower() for c in campione):
        parola = " ".join(w.lower() if i and w.lower() in _PARTICELLE_MINUSCOLE else w[:1] + w[1:].lower()
                          for i, w in enumerate(parola.split()))  # «CERRO AL LAMBRO» scritto «Ravenna» → «Cerro al Lambro»
    pc, pp = campione.split(), parola.split()
    if per_parola and len(pc) == len(pp) > 1:
        return " ".join(_caso_parola(a, b) for a, b in zip(pc, pp))
    lettere = [c for c in campione if c.isalpha()]
    if len(lettere) > 1 and all(c.isupper() for c in lettere):
        return parola.upper()
    if lettere and all(c.islower() for c in lettere):
        return parola.lower()
    return parola


def classe_caso(s: str) -> str:
    """«upper» (lettere quasi tutte maiuscole: «MACLEOD-Wood»), «lower», altrimenti «title»."""
    lettere = [c for c in s if c.isalpha()]
    if not lettere:
        return "title"
    if all(c.islower() for c in lettere):
        return "lower"
    if len(lettere) > 1 and sum(c.isupper() for c in lettere) / len(lettere) > 0.5:
        return "upper"
    return "title"


def canon(tipo: str, s: str) -> str:
    if tipo in ("CF", "IBAN", "TARGA", "DOCUMENTO", "CODICE", "NINO", "PASSAPORTO", "PATENTE", "VIN", "CATASTO", "CONTO"):
        return re.sub(r"[\s\-./]", "", s).upper()
    if tipo == "PRATICA":
        return re.sub(r"\s", "", s).upper()
    if tipo in _CIFRE:
        return re.sub(r"\D", "", re.sub(r"^IT", "", s.strip(), flags=re.I))
    if tipo == "TELEFONO":
        d = re.sub(r"\D", "", s)
        if d.startswith("0039") and len(d) > 11:
            d = d[4:]
        elif d.startswith("39") and len(d) > 10 and s.strip().startswith(("+", "39")):
            d = d[2:]
        return d
    if tipo in ("EMAIL", "DOMINIO", "IP"):
        return s.strip().lower()
    return re.sub(r"\s+", " ", norm(s)).strip()


def _alternanza(parti: list) -> str:
    """Alternativa di molti valori, divisa per iniziale: «(?=[Mm])(?:Mario|Marta…)|(?=[Rr])(?:…)». Il motore prova un
    gruppo solo se la lettera corrisponde: con mille alias il ripristino non prova mille rami a ogni posizione.
    Dentro ogni gruppo resta l'ordine dato (dal più lungo); `cifre` = il valore può cominciare con un numero (CAP, civico)."""
    gruppi: dict = {}
    for iniziale, cifre, pat in parti:
        g = gruppi.setdefault(iniziale.lower(), [set(), []])
        g[0] |= {iniziale.lower(), iniziale.upper()} | ({"0-9"} if cifre else set())
        g[1].append(pat)
    rami = []
    for _, (lettere, pats) in gruppi.items():
        classe = "".join(sorted(re.escape(c) if c != "0-9" else c for c in lettere if c))
        rami.append(f"(?=[{classe}])(?:" + "|".join(pats) + ")" if classe else "(?:" + "|".join(pats) + ")")
    return "|".join(rami)


def _differenze(originale: str, tornato: str, difflib) -> list:
    """Intervalli dell'originale che il ritorno altera. Prima per righe (veloce anche su testi lunghi), poi carattere
    per carattere solo dentro i blocchi di righe diversi."""
    righe_o = originale.splitlines(keepends=True)
    righe_t = tornato.splitlines(keepends=True)
    pos_o = [0]
    for r in righe_o:
        pos_o.append(pos_o[-1] + len(r))
    rotti = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, righe_o, righe_t, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        base = pos_o[i1]
        a_txt, b_txt = "".join(righe_o[i1:i2]), "".join(righe_t[j1:j2])
        for op2, k1, k2, _x, _y in difflib.SequenceMatcher(None, a_txt, b_txt, autojunk=False).get_opcodes():
            if op2 != "equal":
                rotti.append((max(0, base + k1 - 1), min(len(originale), max(base + k2, base + k1 + 1))))
    return rotti


def _lev(a: str, b: str, limite: int = 2) -> int:
    if abs(len(a) - len(b)) > limite:
        return limite + 1
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prec[j] + 1, cur[j - 1] + 1, prec[j - 1] + (ca != cb)))
        prec = cur
    return prec[-1]


class Sessione:
    def __init__(self, config: Configurazione | None = None, id: str | None = None, ner=None,
                 oggi: dt.date | None = None):
        self.config = config or Configurazione()
        self.id = id or secrets.token_hex(6)
        adesso = dt.datetime.now(dt.timezone.utc)
        self.creata = adesso.isoformat()
        self.scadenza = (adesso + dt.timedelta(hours=self.config.scadenza_ore)).isoformat()
        self._rng = random.Random(self.config.seme) if self.config.seme is not None else random.SystemRandom()
        self.delta = scegli_delta(self._rng, self.config.settimane_min, self.config.settimane_max,
                                  self.config.conserva_settimana)
        self.oggi_reale = oggi or dt.date.today()
        self.unita: dict[str, dict] = {}          # norm reale -> {ruolo, r, f, g}
        self.unita_finte: dict[str, str] = {}     # norm finto -> norm reale
        self.persone: list[dict] = []             # {"nomi": [norm], "cognome": norm}
        self.valori: dict[str, dict] = {}         # "TIPO|canon reale" -> {r, f, ...}
        self.valori_finti: dict[str, str] = {}    # "TIPO|canon finto" -> chiave reale
        self.civici: dict[str, str] = {}          # "via finta|civico finto" -> civico reale
        self.cap: dict[str, str] = {}             # "città finta|cap finto" -> cap reale
        self.date_ferme: set[str] = set()
        self.date_finte: list[str] = []           # min e max delle date finte
        self.date_sup: dict[str, str] = {}
        self.date_fidate: set[str] = set()
        self.segnaposti: dict[str, str] = {}   # «⟦S3⟧» -> testo vero (pezzi che con un finto non tornerebbero identici)
        self._n_segnaposto = 0
        self.iniziali: dict[str, str] = {}        # "cognome reale|lettera vera" -> lettera finta        # forma finta -> forma originale («1° ottobre», «03/10»)
        self.ner = ner
        self.ner_atteso = False  # vero mentre il modello si carica: le parole sconosciute si sostituiscono per prudenza
        self._parole_testo: set = set()
        self._cache_ner: dict = {}  # impronta del testo -> entità del modello (solo in memoria): GLiNER è la parte lenta
        self._cache_esiti: dict = {}  # (impronta, modo NER) -> (versione, Esito): la storia della chat non si ricalcola
        self._registrazioni: list = []  # (versione, testo reale in minuscolo) per capire se un esito in memoria è ancora valido
        self.statistiche = {"memoria": 0, "puliti": 0, "regole": 0, "ner": 0, "ner_caratteri": 0}
        self._testo_norm = ""
        self._versione = 0
        self._cache_noti = None
        self._cache_finti = None
        self.convenzione = "DMY"   # date numeriche: «DMY» (Italia, Regno Unito) o «MDY» (Stati Uniti); serve al ripristino
        self.inglese = False       # la sessione ha visto testi in inglese: il ripristino cerca anche gli schemi US/UK
        self._lingua = "it"
        self._uk = False
        self._pool_en = False

    # ------------------------------------------------------------------ utilità
    @property
    def delta_anni(self) -> int:
        return round(self.delta / 365.2425)

    def oggi_fittizio(self, oggi: dt.date | None = None) -> dt.date:
        return (oggi or dt.date.today()) + dt.timedelta(days=self.delta)

    def istruzioni_oggi(self, oggi: dt.date | None = None) -> str:
        """Testo da dare al modello. Di base NON rivela la data di oggi: i calcoli rispetto a oggi
        si fanno sul PC, con marcatori che il ripristino sostituisce con il risultato vero."""
        if self._solo_nascita or not self.config.date:
            return ""  # le date (tranne quelle di nascita) restano vere: il modello conosce già l'oggi vero
        if self.config.dichiara_oggi:
            return self.nota_oggi(oggi)
        return ISTRUZIONI_MARCATORI

    def nota_oggi(self, oggi: dt.date | None = None) -> str:
        """Riga da dare al modello in cloud: la «data di oggi» spostata come tutte le altre date."""
        return (f"Data di oggi: {formato_lungo(self.oggi_fittizio(oggi))}. "
                "Usa questa data come riferimento per età, scadenze e termini.")

    def scaduta(self) -> bool:
        return dt.datetime.now(dt.timezone.utc) > dt.datetime.fromisoformat(self.scadenza)

    def _controlla_scadenza(self):
        if self.scaduta():
            raise SessioneScaduta(f"La sessione {self.id} è scaduta: la mappa non è più utilizzabile.")

    def _toccata(self):
        self._versione += 1
        self._cache_noti = None
        self._cache_finti = None

    def _usati_finti(self) -> set:
        s = set(self.unita_finte)
        s.update(k.split("|", 1)[1] for k in self.valori_finti)
        return s

    # ------------------------------------------------------------------ persone
    def _alias_unita(self, ruolo: str, genere: str | None, vietati: set) -> str:
        if ruolo == "nome":
            if self._pool_en:
                pool = DE.ALIAS_FIRST_F if genere == "F" else DE.ALIAS_FIRST_M
            else:
                pool = dati.ALIAS_NOMI_F if genere == "F" else dati.ALIAS_NOMI_M
        else:
            pool = DE.ALIAS_SURNAMES if self._pool_en else dati.ALIAS_COGNOMI
        usati = set(self.unita_finte) | set(self.unita) | vietati
        scelte = [x for x in pool if norm(x) not in usati]
        if scelte:
            return self._rng.choice(scelte)
        for _ in range(200):
            x = G.sillabe_cognome(self._rng) if ruolo == "cognome" else self._rng.choice(pool) + self._rng.choice(["ina", "etto", "ino", "ella"])
            if norm(x) not in usati:
                return x
        raise RuntimeError("alias esauriti")

    def _registra_unita(self, testo_unita: str, ruolo: str, genere: str | None, vietati: set) -> dict:
        n = re.sub(r"\s+", " ", norm(testo_unita))
        if n in self.unita:
            return self.unita[n]
        if ruolo == "nome" and genere is None:
            genere = R.genere_nome(testo_unita) or DE.genere(testo_unita) or ("F" if n.endswith("a") else "M")
        forma = " ".join(w if not w.isupper() or len(w) < 2 else w.capitalize() for w in testo_unita.split())
        forma = re.sub(r"(['’])(\w)", lambda m: m.group(1) + m.group(2).upper(), forma)
        particelle = re.match(r"((?:(?:De|Di|Del|Della|Dello|Dei|Degli|Da|Dal|Dalla|La|Lo|Li|Le|El|Van|Von|Ben)\s+)+)", forma)
        basi = {norm(u["f"].split()[-1]) for u in self.unita.values()}
        for _ in range(500):
            alias = self._alias_unita(ruolo, genere, vietati)
            if ruolo == "cognome" and particelle and len(forma.split()) > 1:
                alias = particelle.group(1) + alias  # «Di Bergamo» → «Di Zanoni»: stesso numero di parole
            if norm(alias) not in self.unita_finte and norm(alias.split()[-1]) not in basi:
                break
        voce = {"ruolo": ruolo, "r": forma, "f": alias, "g": genere}
        self.unita[n] = voce
        self.unita_finte[norm(alias)] = n
        self._registrazioni.append((self._versione + 1, forma.lower()))
        self._toccata()
        return voce

    def registra_persona(self, nome: str | None, cognome: str | None, genere: str | None = None,
                         vietati: set | None = None) -> dict:
        """Registra una persona nota (es. colonne Nome/Cognome di un foglio). Restituisce gli alias."""
        vietati = vietati or set()
        nomi = []
        for parola in (nome or "").split():
            v = self._registra_unita(parola, "nome", genere or R.genere_nome(parola), vietati)
            nomi.append(norm(parola))
        cg = None
        if cognome and cognome.strip():
            self._registra_unita(cognome.strip(), "cognome", None, vietati)
            cg = re.sub(r"\s+", " ", norm(cognome.strip()))
        p = {"nomi": nomi, "cognome": cg}
        if p not in self.persone and (nomi or cg):
            self.persone.append(p)
        if nomi and cg:  # «Mario Rossi» → «Luca Galimberti»: allora «M. Rossi» → «L. Galimberti», se la lettera è libera
            chiave, f = f"{cg}|{self.unita[nomi[0]]['r'][0].upper()}", self.unita[nomi[0]]["f"][0].upper()
            usate = {v for k, v in self.iniziali.items() if k.startswith(cg + "|")}
            if chiave not in self.iniziali and f not in usate:
                self.iniziali[chiave] = f
        return {"nome": " ".join(self.unita[n]["f"] for n in nomi) if nomi else None,
                "cognome": self.unita[cg]["f"] if cg else None}

    # ------------------------------------------------------------------ forme superficiali
    def _forma_finta(self, voce: dict, reale: str, finto: str, per_parola: bool = True) -> str:
        """Forma del finto con la stessa classe di maiuscole del vero; la forma vera si ricorda per il ritorno esatto."""
        cls = classe_caso(reale)
        out = finto.upper() if cls == "upper" else finto.lower() if cls == "lower" else applica_caso(reale, finto, per_parola)
        if classe_caso(out) != cls and cls == "title":
            out = finto
        sup = voce.setdefault("superfici", {})
        if cls not in sup:
            sup[cls] = reale
            self._toccata()
        return out

    def _forma_vera(self, voce: dict, finto_visto: str, per_parola: bool = True) -> str:
        sup = voce.get("superfici", {}).get(classe_caso(finto_visto))
        if sup is not None and (classe_caso(finto_visto) != "title" or finto_visto[:1].isupper()):
            return sup
        return applica_caso(finto_visto, voce["r"], per_parola)

    # ------------------------------------------------------------------ valori
    def _valore(self, tipo: str, reale: str, crea) -> dict:
        chiave = f"{tipo}|{canon(tipo, reale)}"
        v = self.valori.get(chiave)
        if v is None:
            usati = self._usati_finti()
            for _ in range(500):
                finto = crea()
                cf = canon(tipo, finto["f"] if isinstance(finto, dict) else finto)
                if cf not in usati and cf != canon(tipo, reale) and f"{tipo}|{cf}" not in self.valori_finti:
                    break
            else:  # mai due dati veri sullo stesso finto: il ripristino li confonderebbe
                if tipo in TIPI_SCHEMA or tipo == "EMAIL":
                    raise RuntimeError(f"nessun valore finto libero per il tipo {tipo}")
                log.warning("alias ripetuto per il tipo %s: il ripristino segnalerà le occorrenze ambigue", tipo)
            v = finto if isinstance(finto, dict) else {"f": finto}
            v["r"] = reale
            self.valori[chiave] = v
            self.valori_finti[f"{tipo}|{canon(tipo, v['f'])}"] = chiave
            self._registrazioni.append((self._versione + 1, str(reale).lower()))
            self._toccata()
        return v

    def _finto_cf(self, reale: str) -> str:
        def crea():
            info = V.decodifica_cf(reale, self.oggi_reale)
            s = reale.upper()
            persona = None
            for p in self.persone:
                cg = self.unita.get(p["cognome"] or "")
                nm = self.unita.get(p["nomi"][0]) if p["nomi"] else None
                if cg and nm and V.codice_cognome(cg["r"]) + V.codice_nome(" ".join(self.unita[n]["r"] for n in p["nomi"])) == s[:6]:
                    persona = (cg["f"], " ".join(self.unita[n]["f"] for n in p["nomi"]))
                    break
            if persona is None:
                persona = (self._rng.choice(dati.ALIAS_COGNOMI), self._rng.choice(dati.ALIAS_NOMI_M + dati.ALIAS_NOMI_F))
            if info:
                nascita = info["nascita"] + dt.timedelta(days=self.delta)
                sesso = info["sesso"]
                comune = self._comune_cf(info["comune"])
            else:
                nascita = dt.date(self._rng.randint(1950, 2000), self._rng.randint(1, 12), self._rng.randint(1, 28))
                sesso, comune = self._rng.choice("MF"), self._rng.choice(dati.COMUNI)[3]
            return V.genera_cf(persona[0], persona[1], nascita, sesso, comune)
        return self._valore("CF", reale, crea)["f"]

    def _comune_cf(self, codice_reale: str) -> str:
        reale = next((c for c in dati.COMUNI if c[3] == codice_reale), None)
        if reale:
            v = self.valori.get(f"CITTA|{canon('CITTA', reale[0])}")
            if v:
                return v["fcod"]
        return self._valore("CODCOMUNE", codice_reale, lambda: self._rng.choice(dati.COMUNI)[3])["f"]

    def _citta(self, nome: str, sigla: str | None = None, cap: str | None = None) -> dict:
        cache: dict = {}

        def crea():  # gli insiemi da evitare si calcolano una volta sola per città (non a ogni tentativo)
            if "v" not in cache:
                cache["v"] = {nome} | {self.valori[k]["f"] for k in self.valori if k.startswith("CITTA|")}
            vietate = cache["v"]
            if self._lingua != "it" and norm(nome) not in dati.LUOGHI_IT:
                if "en" not in cache:
                    cache["en"] = vietate | {c[0] for c in DE.US_CITIES + DE.UK_TOWNS if norm(c[0]) in self._testo_norm}
                al = EN.finta_citta(self._rng, self._uk, cache["en"])
                return {"f": al[0], "fs": al[1] if len(al[1]) == 2 else "", "fcap": al[2], "fcod": "", "en": True}
            if "it" not in cache:
                cache["it"] = vietate | {c[0] for c in dati.COMUNI if norm(c[0]) in self._parole_testo}
            al = G.finto_comune(self._rng, cache["it"])
            return {"f": al[0], "fs": al[1], "fcap": al[2], "fcod": al[3]}
        v = self._valore("CITTA", nome, crea)
        if sigla:
            v.setdefault("rs", sigla)
        return v

    def _cap_finto(self, citta_v: dict, cap_reale: str) -> str:
        chiave_rev = None
        for k, r in self.cap.items():
            if k.startswith(norm(citta_v["f"]) + "|") and r == cap_reale:
                chiave_rev = k.split("|", 1)[1]
        if chiave_rev:
            return chiave_rev
        for _ in range(100):
            c = citta_v["fcap"][:3] + G.cifre_casuali(self._rng, 2)
            if f"{norm(citta_v['f'])}|{c}" not in self.cap:
                break
        self.cap[f"{norm(citta_v['f'])}|{c}"] = cap_reale
        self._toccata()
        return c

    def _finto_email(self, reale: str) -> str:
        def crea():
            locale, dominio = reale.rsplit("@", 1)
            nuovo_locale = self._sostituisci_in_minuscolo(locale)
            if nuovo_locale == locale:
                nuovo_locale = G.come_classi(self._rng, locale).lower()
            return f"{nuovo_locale}@{self._finto_dominio(dominio)}"
        return self._valore("EMAIL", reale, crea)["f"]

    def _finto_dominio(self, dominio: str) -> str:
        d = dominio.lower()
        if d in dati.DOMINI_PUBBLICI:
            return dominio
        parti = d.split(".")
        if len(parti) < 2:
            return dominio
        base = ".".join(parti[-2:]) if not (len(parti) >= 3 and parti[-2] in ("co", "com", "gov", "edu")) else ".".join(parti[-3:])
        def crea():
            etichetta = self._sostituisci_in_minuscolo(base.split(".")[0])
            if etichetta == base.split(".")[0]:
                etichetta = self._rng.choice(dati.ALIAS_PAROLE_DOMINIO) + str(self._rng.randint(1, 99))
            return etichetta + base[base.index("."):]
        finto_base = self._valore("DOMINIO", base, crea)["f"]
        return d[: len(d) - len(base)] + finto_base

    def _sostituisci_in_minuscolo(self, s: str) -> str:
        """Sostituisce le unità di nome note dentro stringhe minuscole (mario.rossi → luca.galimberti)."""
        if not self.unita:
            return s
        unita = sorted(self.unita.items(), key=lambda kv: -len(kv[0]))
        rx = re.compile("|".join(re.escape(k.replace(" ", "")) for k, _ in unita if len(k) >= 3), re.I)
        mappa = {k.replace(" ", ""): norm(v["f"]).replace(" ", "").replace("'", "") for k, v in unita}
        return rx.sub(lambda m: mappa.get(norm(m.group(0)), m.group(0)), s) if rx.pattern else s

    # ------------------------------------------------------------------ pseudonimizzazione
    @property
    def _solo_nascita(self) -> bool:
        return self.config.date == "nascita"

    def pseudonimizza(self, testo: str, usa_ner: bool | str = True, ner_massimo: int | None = None) -> Esito:
        """usa_ner: True = modello su tutto il testo; False = solo regole; «auto» = prefiltro e modello solo sulle frasi
        con parole maiuscole sconosciute (nomi rari, soprannomi, paesi piccoli). Gli esiti restano in memoria finché
        nessun dato registrato dopo compare nel testo."""
        self._controlla_scadenza()
        if usa_ner is True and self.config.ner_modo == "auto":
            usa_ner = "auto"
        import hashlib
        chiave = (hashlib.sha256(testo.encode("utf-8")).hexdigest(), str(usa_ner))
        voce = self._cache_esiti.get(chiave)
        if voce is not None:
            if voce[0] == self._versione or self._ancora_valido(testo, voce[0]):
                self._cache_esiti[chiave] = (self._versione, voce[1])
                self.statistiche["memoria"] += 1
                return voce[1]
        self._modo = self.config.modalita
        if self.config.fuga_sensibili and self._modo != "fuga" and R.testo_sensibile(testo[:30000]):
            self._modo = "fuga"  # referti, cartelle, atti, sentenze: nel dubbio si sostituisce
        if len(testo) > 6000:  # testi lunghi (prompt di sistema, contesto, PDF): si analizzano solo i blocchi che servono
            e = self._a_blocchi(testo, usa_ner, ner_massimo)
            if len(self._cache_esiti) > 4096:
                self._cache_esiti.pop(next(iter(self._cache_esiti)))
            self._cache_esiti[chiave] = (self._versione, e)
            return e
        p = PF.esamina(testo, frozenset(self.unita))
        if p["pulito"] and (not (self.unita or self.valori or self.date_sup or self.segnaposti)
                            or self.ripristina(testo, controllo=True).testo == testo):
            e = Esito(testo)  # niente da sostituire, e il ritorno lo lascerebbe identico
            self.statistiche["puliti"] += 1
        else:
            ignote = p["ignote"] if usa_ner == "auto" else None
            e = self._pseudonimizza(testo, bool(usa_ner) and (ignote is None or bool(ignote)), None, ignote, ner_massimo)
        if len(self._cache_esiti) > 4096:
            self._cache_esiti.pop(next(iter(self._cache_esiti)))
        self._cache_esiti[chiave] = (self._versione, e)
        return e

    def _a_blocchi(self, testo: str, usa_ner, ner_massimo) -> Esito:
        """Divide il testo alle righe vuote; i blocchi in cui il prefiltro non vede nulla di personale (e che il ritorno
        lascerebbe identici) restano com'erano, gli altri si analizzano a gruppi con la lingua e la convenzione delle date
        dell'intero documento. È ciò che rende veloce la prima richiesta con un prompt di sistema di 80.000 caratteri."""
        campione = testo[:20000]
        lingua = EN.lingua(campione)
        conv = convenzione_date(campione, lingua)
        pezzi = re.split(r"(\n[ \t]*\n|(?<=[.!?])[ \t]+(?=[A-Z])|\n)", testo)  # paragrafi, righe e frasi
        blocchi, cur = [], 0
        for i, pz in enumerate(pezzi):
            blocchi.append((cur, cur + len(pz), i % 2 == 1))
            cur += len(pz)
        mappa = bool(self.unita or self.valori or self.date_sup or self.segnaposti)
        minuscole = PF.parole_minuscole(testo)
        sporchi = []
        unita = frozenset(self.unita)
        for a, b, sep in blocchi:
            sporchi.append(None if sep else not PF.esamina(testo[a:b], unita, minuscole)["pulito"])
        # un solo ripristino di prova, sui soli blocchi puliti (gli altri si analizzano comunque): quelli che il
        # ritorno cambierebbe vanno analizzati anche loro. Controllo incrementale: i blocchi sporchi non si rileggono.
        if mappa:
            puliti = [(a, b) for (a, b, sep), s in zip(blocchi, sporchi) if s is False and b > a]
            prova, posizioni, cur = [], [], 0
            for a, b in puliti:
                posizioni.append((cur, a))
                prova.append(testo[a:b])
                cur += b - a + 2
            testo_prova = "\n\n".join(prova)
            toccati = Intervalli()
            from bisect import bisect_right
            inizi = [p for p, _ in posizioni]
            for x, y, n, _ in self.ripristina(testo_prova, controllo=True).sostituzioni:
                if n != testo_prova[x:y]:
                    k = bisect_right(inizi, x) - 1
                    base = posizioni[k][1] - posizioni[k][0]
                    toccati.aggiungi(x + base, y + base) if toccati.libero(x + base, y + base) else None
            for k, (a, b, sep) in enumerate(blocchi):
                if sporchi[k] is False and not toccati.libero(a, b):
                    sporchi[k] = True
        # gruppi di blocchi sporchi consecutivi (con le righe vuote in mezzo)
        gruppi, inizio = [], None
        for k, (a, b, sep) in enumerate(blocchi):
            stato = sporchi[k]
            if stato is None:
                continue
            if stato and inizio is None:
                inizio = a
            if not stato and inizio is not None:
                gruppi.append((inizio, blocchi[k - 1][0] if blocchi[k - 1][2] else a))
                inizio = None
        if inizio is not None:
            gruppi.append((inizio, len(testo)))
        uniti = []  # gruppi vicini restano insieme: date relative, intestazioni e firme devono vedere il loro contesto
        for a, b in gruppi:
            if uniti and a - uniti[-1][1] < 2000:
                uniti[-1] = (uniti[-1][0], b)
            else:
                uniti.append((a, b))
        gruppi = uniti
        out, cur, sostituzioni, conteggi, avvisi, dettagli = [], 0, [], {}, [], []
        for a, b in gruppi:
            seg = testo[a:b]
            p = PF.esamina(seg, frozenset(self.unita))
            ignote = p["ignote"] if usa_ner == "auto" else None
            e = self._pseudonimizza(seg, bool(usa_ner) and (ignote is None or bool(ignote)), None, ignote, ner_massimo,
                                    lingua=lingua, conv=conv)
            out += [testo[cur:a], e.testo]
            cur = b
            sostituzioni += [(x + a, y + a, n, t) for x, y, n, t in e.sostituzioni]
            for k2, v in e.conteggi.items():
                conteggi[k2] = conteggi.get(k2, 0) + v
            avvisi += [x for x in e.avvisi if x not in avvisi]
            dettagli += e.dettagli
        out.append(testo[cur:])
        self.statistiche["puliti"] += len([x for x in sporchi if x is False])
        return Esito("".join(out), sostituzioni, conteggi, avvisi, [], dettagli)

    def _ancora_valido(self, testo: str, versione: int) -> bool:
        nuovi = [s for v, s in self._registrazioni if v > versione]
        if not nuovi:
            return True
        basso = testo.lower()
        return not any(s and s in basso for s in nuovi)

    def _pseudonimizza(self, testo: str, usa_ner: bool, zone: list | None, ignote: list | None = None,
                       ner_massimo: int | None = None, lingua: str | None = None, conv: str | None = None) -> Esito:
        cfg = self.config
        avvisi: list[str] = []
        self.statistiche["regole"] += 1
        # Collisione: un alias già usato compare davvero nel testo nuovo (il ripristino lo confonderebbe).
        for fn in self._finti_presenti(testo):
            avvisi.append(f"collisione: un alias della sessione compare nel testo originale ({len(fn)} caratteri); "
                          "le sue occorrenze andranno verificate dopo il ripristino")
        modo = getattr(self, "_modo", cfg.modalita)
        schemi = R.trova_schemi(testo, modo, sanitari=cfg.sanitari != "lascia")
        if cfg.aziende:
            schemi += R.trova_aziende(testo)
        if not cfg.citta:
            schemi = [s for s in schemi if s.tipo not in ("CITTA", "CAP_CITTA")]
        persone = R.candidati_persone(testo, modo)
        if self.ner is not None and usa_ner and ignote is not None:
            # modalità «auto»: il modello solo sulle frasi con parole sconosciute che le regole non hanno già coperto
            coperti = [(x.inizio, x.fine) for x in schemi] + [(x.inizio, x.fine) for x in persone]
            scoperte = [(a, b) for a, b in ignote if not any(x <= a and b <= y for x, y in coperti)]
            zone = PF.frasi_con(testo, scoperte, margine=160)  # un po' di contesto attorno: meno falsi positivi
            if ner_massimo is not None:
                tagliate, resto = [], ner_massimo
                for a, b in zone:
                    if resto <= 0:
                        break
                    tagliate.append((a, min(b, a + resto)))
                    resto -= b - a
                zone = tagliate
            if zone:
                persone += self._da_ner(testo, schemi, avvisi, zone)
        elif self.ner is not None and usa_ner:
            persone += self._da_ner(testo, schemi, avvisi, zone)
        lingua = lingua or EN.lingua(testo)
        self._lingua = lingua
        if lingua == "it":  # «+44 7700 900263», «+1 305 555 0187» in un testo italiano
            schemi += [x for x in EN.trova_telefoni_esteri(testo)] + EN.indirizzi_esteri(testo)
        if lingua != "it":
            self.inglese = True
            self._uk = EN.paese(testo[:20000]) == "UK"
            if lingua == "en":  # numeri italiani solo con +39: «045-123456» in un testo inglese non è un telefono
                schemi = [s for s in schemi if not (s.tipo == "TELEFONO" and s.confidenza < 0.95
                                                    and not s.testo.lstrip().startswith(("+39", "0039")))]
                # «VIA CERTIFIED MAIL»: in inglese «via» non apre un indirizzo (salvo «Via Roma» con un nome italiano)
                schemi = [s for s in schemi if not (s.tipo == "INDIRIZZO" and not s.meta.get("en") and (
                    s.testo.split()[0].isupper() or norm(s.meta.get("via", "x").split()[0]) in DE.COMMON_WORDS))]
            schemi += [s for s in EN.trova_schemi_en(testo) if cfg.citta or s.tipo != "CITTA"]
            persone += EN.candidati_persone_en(testo)
        conv = conv or convenzione_date(testo[:30000], lingua)
        if lingua != "it" or conv == "MDY":  # «02/28/2025» in un testo breve letto come italiano: vale lo stesso
            self.convenzione = conv
        if self.ner is None and self.ner_atteso and ignote:
            # modello non ancora pronto (primi secondi dopo l'avvio): le parole maiuscole sconosciute non coperte dalle
            # regole si trattano come nomi propri, come in modalità «fuga». Meglio un falso positivo che un nome in chiaro.
            coperti = [(x.inizio, x.fine) for x in schemi] + [(x.inizio, x.fine) for x in persone]
            for a, b in ignote:
                if not any(x <= a and b <= y for x, y in coperti):
                    persone.append(R.PersonaCandidata(a, b, [(a, b, testo[a:b])], None, 0.5, "attesa-modello"))
        date = trova_date(testo, self.oggi_reale.year, cfg.anni_contesto, conv) if cfg.date else []
        if self._solo_nascita:  # solo le date di nascita si spostano; le altre restano vere ma proteggono dai falsi «telefoni»
            for d in date:
                d.ferma = not (d.granularita == "giorno" and RE_CONTESTO_NASCITA.search(testo[max(0, d.inizio - 40):d.inizio]))
        span_date = [R.Span(d.inizio, d.fine, "DATA", d.testo, 1.0, {"data": d}) for d in date]
        # Un numero che è una data valida non è un telefono (salvo indizio esplicito «tel.»).
        schemi = [s for s in schemi if not ((s.tipo == "TELEFONO" and s.confidenza < 0.95 or s.confidenza <= 0.5) and
                                            any(d.inizio < s.fine and s.inizio < d.fine for d in span_date))]
        prelim = schemi + span_date + [R.Span(p.inizio, p.fine, "PERSONA", testo[p.inizio:p.fine], p.confidenza,
                                              {"cand": p}) for p in persone]
        scelti = R.arbitra(prelim)
        # Le aziende non vanno spezzate dai nomi di persona dentro la ragione sociale.
        vietati = {norm(w) for w in re.findall(r"[\w'’]+", testo)}
        self._testo_norm = norm(testo)
        self._parole_testo = vietati | {norm(m) for m in re.findall(r"[A-ZÀ-Ý][\w'’]+(?:\s[A-ZÀ-Ý][\w'’]+)+", testo)}
        for s in scelti:
            if s.tipo == "PERSONA":
                p = s.meta["cand"]
                nomi, cognome = [], None
                en = p.fonte in _FONTI_EN or (lingua != "it" and p.fonte in ("ner", "attesa-modello"))
                italiani = all(norm(w[2]) in R.NOMI or norm(w[2]) in R.COGNOMI for w in p.parole)
                self._pool_en = lingua != "it" and not italiani  # nomi italiani in un testo inglese restano italiani
                ruoli = p.ruoli or (EN.ruoli_en(p.parole) if en and not italiani else R.ruoli(p.parole, p.genere))
                for ruolo, a, b, _ in ruoli:
                    if ruolo == "nome":
                        nomi.append(testo[a:b])
                    else:
                        cognome = testo[a:b]
                self.registra_persona(" ".join(nomi) or None, cognome, p.genere, vietati)
                if p.fonte == "minuscolo":  # le occorrenze in minuscolo di questo nome vanno sostituite e ripristinate
                    for w in nomi:
                        if norm(w) in self.unita and not self.unita[norm(w)].get("min"):
                            self.unita[norm(w)]["min"] = True
                            self._toccata()
                self._pool_en = False
        # Prima le città (servono ai codici fiscali), poi il resto.
        sost: list[tuple] = []
        dettagli: list[tuple] = []
        for s in scelti:
            if s.tipo in ("CITTA", "CAP_CITTA"):
                self._prepara_citta(testo, s)
        for s in scelti:
            if s.tipo == "PERSONA":
                continue
            r = self._sostituto(testo, s, avvisi)
            if r is not None:
                sost.append((s.inizio, s.fine, r, s.tipo))
                dettagli.append((s.tipo, s.testo, r))
        # Occorrenze dei valori già noti (anche di documenti precedenti) e delle unità di nome.
        noti = self._occorrenze_note(testo)
        tutti = [R.Span(a, b, t, testo[a:b], 1.0, {"nuovo": n}) for a, b, n, t in sost] + noti
        finali = R.arbitra(tutti)
        out, cur, sostituzioni, conteggi = [], 0, [], {}
        for s in finali:
            nuovo = s.meta["nuovo"]
            if nuovo is None:
                continue
            out.append(testo[cur:s.inizio])
            out.append(nuovo)
            cur = s.fine
            sostituzioni.append((s.inizio, s.fine, nuovo, s.tipo))
            t = "PERSONA" if s.tipo in ("NOME", "COGNOME", "INIZIALE") else s.tipo
            conteggi[t] = conteggi.get(t, 0) + 1
            if s.tipo in ("NOME", "COGNOME", "INIZIALE"):
                dettagli.append((s.tipo, s.testo, nuovo))
        out.append(testo[cur:])
        risultato = "".join(out)
        risultato, sostituzioni, n_segnaposti = self._garantisci_ritorno(testo, risultato, sostituzioni)
        if n_segnaposti:
            conteggi["SEGNAPOSTO"] = n_segnaposti
            avvisi.append(f"{n_segnaposti} pezzi sostituiti con un segnaposto ⟦S…⟧: con un dato finto il ritorno non "
                          "sarebbe stato identico all'originale")
        for s in scelti:
            if s.tipo == "SANITARIO" and cfg.sanitari == "segnala":
                conteggi["SANITARIO_SEGNALATO"] = conteggi.get("SANITARIO_SEGNALATO", 0) + 1
        if conteggi.get("SANITARIO_SEGNALATO"):
            avvisi.append(f"{conteggi['SANITARIO_SEGNALATO']} dati sanitari lasciati in chiaro (le persone sono "
                          "comunque sostituite); usare sanitari='sostituisci' per cambiarli")
        rilevati = [(s.tipo, s.testo) for s in scelti if s.tipo in TIPI_SCHEMA + ("EMAIL",)]
        fughe = self.controlla_fughe(testo, risultato, rilevati)
        if fughe:
            msg = f"{len(fughe)} dati originali ancora presenti dopo la sostituzione ({', '.join(sorted(set(fughe)))})"
            if cfg.modalita == "fuga" and cfg.blocca_fughe:
                raise FugaRilevata(msg)
            avvisi.append(msg)
        log.info("pseudonimizza sessione=%s sostituzioni=%s avvisi=%d", self.id,
                 {k: v for k, v in sorted(conteggi.items())}, len(avvisi))
        return Esito(risultato, sostituzioni, conteggi, avvisi, [], dettagli)

    # ------------------------------------------------------------------ controllo di invarianza
    def _garantisci_ritorno(self, originale: str, finto: str, sostituzioni: list) -> tuple[str, list, int]:
        """Andata e ritorno senza modello: ripristina(finto) deve dare l'originale byte per byte. Dove non è così, il pezzo
        (la sostituzione coinvolta, o il testo vero che il ripristino altererebbe) diventa un segnaposto ⟦Sn⟧ che torna
        esatto. Mai un testo alterato."""
        if not (self.unita or self.valori or self.date_sup or self.segnaposti):
            return finto, sostituzioni, 0
        import difflib
        usati = 0
        for _ in range(4):
            tornato = self.ripristina(finto, controllo=True).testo
            if tornato == originale:
                return finto, sostituzioni, usati
            rotti = _differenze(originale, tornato, difflib)
            # pezzi da coprire: le sostituzioni toccate, oppure il testo vero attorno al punto alterato (parole intere)
            pezzi = []
            for a, b in rotti:
                toccate = [(x, y) for x, y, _, _ in sostituzioni if x < b and a < y]
                if toccate:
                    pezzi += toccate
                else:
                    while a > 0 and not originale[a - 1].isspace():
                        a -= 1
                    while b < len(originale) and not originale[b].isspace():
                        b += 1
                    pezzi.append((a, b))
            pezzi.sort()
            uniti = []
            for a, b in pezzi:
                if uniti and a <= uniti[-1][1]:
                    uniti[-1] = (uniti[-1][0], max(uniti[-1][1], b))
                else:
                    uniti.append((a, b))
            nuove = [x for x in sostituzioni if not any(a < x[1] and x[0] < b for a, b in uniti)]
            for a, b in uniti:
                for x in sostituzioni:  # un segnaposto copre per intero le sostituzioni che tocca
                    if a < x[1] and x[0] < b:
                        a, b = min(a, x[0]), max(b, x[1])
                self._n_segnaposto += 1
                tok = f"⟦S{self._n_segnaposto}⟧"
                self.segnaposti[tok] = originale[a:b]
                nuove.append((a, b, tok, "SEGNAPOSTO"))
                usati += 1
            nuove.sort()
            pulite = []
            for x in nuove:  # due segnaposti che si sovrappongono: resta il più largo
                if pulite and x[0] < pulite[-1][1]:
                    if x[1] - x[0] > pulite[-1][1] - pulite[-1][0]:
                        pulite[-1] = x
                    continue
                pulite.append(x)
            sostituzioni = pulite
            out, cur = [], 0
            for a, b, n, _ in sostituzioni:
                out += [originale[cur:a], n]
                cur = b
            out.append(originale[cur:])
            finto = "".join(out)
            self._toccata()
        # ultima difesa: tutto il testo come segnaposto (non succede sui banchi, ma il testo alterato non deve uscire)
        self._n_segnaposto += 1
        tok = f"⟦S{self._n_segnaposto}⟧"
        self.segnaposti[tok] = originale
        log.warning("controllo di invarianza: testo intero sostituito da un segnaposto")
        return tok, [(0, len(originale), tok, "SEGNAPOSTO")], usati + 1

    def ner_memorizzato(self, testo: str) -> bool:
        import hashlib
        return self.ner is not None and hashlib.sha256(testo.encode("utf-8")).hexdigest() in self._cache_ner

    def _da_ner(self, testo, schemi, avvisi, zone=None) -> list:
        import hashlib
        trovati = []
        try:
            for a, b in (zone if zone else [(0, len(testo))]):
                pezzo = testo[a:b]
                chiave = hashlib.sha256(pezzo.encode("utf-8")).hexdigest()
                t = self._cache_ner.get(chiave)
                if t is None:
                    t = self.ner.riconosci(pezzo)
                    self.statistiche["ner"] += 1
                    self.statistiche["ner_caratteri"] += len(pezzo)
                    if len(self._cache_ner) > 2048:
                        self._cache_ner.pop(next(iter(self._cache_ner)))
                    self._cache_ner[chiave] = t
                trovati += [{**x, "inizio": x["inizio"] + a, "fine": x["fine"] + a} for x in t]
        except Exception as e:  # il modello è un aiuto, le regole restano
            avvisi.append(f"riconoscitore NER non disponibile ({type(e).__name__}): restano le regole")
            return []
        out = []
        organizzazioni = [(x["inizio"], x["fine"]) for x in trovati if x["tipo"] == "ORGANIZZAZIONE"]
        for x in trovati:
            pezzo = testo[x["inizio"]:x["fine"]]
            if chr(10) in pezzo.strip():
                continue  # un'entità a cavallo di due righe è quasi sempre un errore del modello
            if x["tipo"] == "PERSONA":
                if any(a <= x["inizio"] and x["fine"] <= b for a, b in organizzazioni):
                    continue  # «Rosa Verde» dentro «Rosa Verde S.n.c.» è un'azienda
                parole = [(m.start() + x["inizio"], m.end() + x["inizio"], m.group(0))
                          for m in re.finditer(r"[\w'’-]+(?:\.(?=\w))?", pezzo)]
                parole = [p for p in parole if p[2][:1].isupper() and len(p[2]) > 1 and not R._non_nome(p[2])
                          and dati.norm(p[2]) not in DE.COMMON_WORDS
                          and not re.fullmatch(r"(?:[LlDd]|[Dd]ell|[Dd]all|[Nn]ell|[Ss]ull|[Uu]n)['’][a-zà-ÿ]\S*", p[2])]  # «L'attore», «D'accordo»
                for k in range(1, len(parole)):  # «Rosa De La Cruz», «Pieter van der Berg»: le particelle vanno col cognome
                    mezzo = testo[parole[k - 1][1]:parole[k][0]]
                    pm = re.fullmatch(r"(\s+)((?:(?:van|von|der|den|de|la|le|da|di|del|della|dos|das|y|ap|bin|ibn|al)\s+)+)", mezzo, re.I)
                    if pm:
                        a = parole[k - 1][1] + len(pm.group(1))
                        parole[k] = (a, parole[k][1], testo[a:parole[k][1]])
                part = re.search(r"(?:^|[\s(])((?:De|Di|Del|Della|Da|Dal|La|Lo|Li|Le|El|DE|DI|DEL|DELLA|DA|LA|LO|LI|D'|DELL')\s?)$", testo[max(0, x["inizio"] - 8):x["inizio"]])
                if parole and part and part.group(1).strip():
                    a = x["inizio"] - len(part.group(1))
                    p0 = parole[0]
                    parole[0] = (a, p0[1], testo[a:p0[1]])  # la particella fa parte del cognome: «LA ROCCA»
                if parole:
                    out.append(R.PersonaCandidata(parole[0][0], parole[-1][1], parole, None, x.get("punteggio", 0.8), "ner"))
            elif x["tipo"] == "LUOGO" and self.config.citta:
                if not pezzo[:1].isupper() or dati.norm(pezzo) in dati.NON_NOMI or re.search(r"\d", pezzo):
                    continue
                schemi.append(R.Span(x["inizio"], x["fine"], "CITTA", pezzo, x.get("punteggio", 0.8)))
            elif x["tipo"] == "CODICE":
                v = pezzo.strip(" .,;:")
                a = x["inizio"] + pezzo.find(v)
                cifre = sum(c.isdigit() for c in v)
                if ((cifre >= 5 or (cifre >= 3 and any(c.isalpha() for c in v))) and " " not in v and len(v) <= 30
                        and not trova_date(v) and not re.search(r"[€$]|\d,\d{2}$", v)):
                    schemi.append(R.Span(a, a + len(v), "CODICE", v, x.get("punteggio", 0.8)))
            elif x["tipo"] == "ORGANIZZAZIONE" and self.config.aziende:
                schemi.append(R.Span(x["inizio"], x["fine"], "AZIENDA", pezzo, x.get("punteggio", 0.8),
                                     {"nome": pezzo, "forma": "", "nome_fine": x["fine"]}))
        return out

    def _prepara_citta(self, testo: str, s: R.Span):
        if s.tipo == "CAP_CITTA":
            m = re.match(r"(\d{5})", s.testo)
            nome = s.meta["citta"]
            sig = re.search(r"\(([A-Z]{2})\)\s*$", s.testo)
            self._citta(nome, sig.group(1) if sig else None)
        elif s.meta.get("stato"):
            self._citta(s.meta["citta"])
        else:
            nome = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", s.testo)
            sig = re.search(r"\(([A-Z]{2})\)\s*$", s.testo)
            self._citta(nome, sig.group(1) if sig else None)

    def _sostituto(self, testo: str, s: R.Span, avvisi: list) -> str | None:
        t, v = s.tipo, s.testo
        rng = self._rng
        if t == "DATA":
            d: DataTrovata = s.meta["data"]
            if getattr(d, "ferma", False):
                return None
            if d.normativa:
                self.date_ferme.add(d.data.isoformat())
                return None
            nuovo = sposta(d, testo, self.delta, self._lingua != "it")
            if self.date_sup.get(nuovo, d.testo) != d.testo:  # «2/10/2025» e «02/10/2025» non devono dare la stessa forma finta
                nuovo = sposta(d, testo, self.delta, self._lingua != "it", zeri_come_originale=True)
            if nuovo not in self.date_sup:
                self.date_sup[nuovo] = d.testo
                if d.speciale.get("tipo") or d.granularita == "giorno_senza_anno":
                    self.date_fidate.add(nuovo)  # forma speciale («3 u.s.», «dal 3»): si torna solo dalla forma salvata
            finta = (d.data + dt.timedelta(days=self.delta)).isoformat()
            self.date_finte = [min(self.date_finte + [finta]), max(self.date_finte + [finta])]
            if (self.config.eta_locale and not self.config.dichiara_oggi and not self._solo_nascita and d.granularita == "giorno"
                    and RE_CONTESTO_NASCITA.search(testo[max(0, d.inizio - 40):d.inizio])):
                anni = _anni_compiuti(d.data, dt.date.today())
                if 0 <= anni < 125:
                    nuovo += f" [age {anni}]" if self._lingua == "en" else f" [età {anni} ann{'o' if anni == 1 else 'i'}]"
            return nuovo
        if t == "CF":
            return G.stampo(v, self._finto_cf(v))
        if t == "PIVA":
            f = self._valore("PIVA", v, lambda: G.finto_piva(rng))["f"]
            pref = re.match(r"IT\s?", v)
            return (pref.group(0) if pref else "") + f
        if t == "IBAN":
            return G.stampo(v, self._valore("IBAN", v, lambda: G.finto_iban(rng, v, self.config.iban_banca))["f"])
        if t == "CARTA":
            return G.stampo(v, self._valore("CARTA", v, lambda: G.finta_carta(rng, v))["f"])
        if t in TIPI_EN:
            crea = {"SSN": lambda: EN.finto_ssn(rng), "ITIN": lambda: EN.finto_itin(rng), "NINO": lambda: EN.finto_nino(rng),
                    "NHS": lambda: EN.finto_nhs(rng), "ROUTING": lambda: EN.finto_aba(rng)}.get(t)
            if crea is None:
                c = canon(t, v)
                prove = [0]

                def crea():  # valori corti («foglio 9», «sezione B»): se le forme libere finiscono, un carattere in più
                    prove[0] += 1
                    extra = prove[0] // 60
                    if c.isdigit():
                        return G.cifre_casuali(rng, len(c) + extra, c[0] != "0")
                    return canon(t, G.finto_documento(rng, c + "X" * extra))
            return G.stampo(v, self._valore(t, v, crea)["f"])
        if t == "TELEFONO" and self._lingua != "it":
            f_en = EN.finto_tel_en(rng, v)
            if f_en is not None:
                f = self._valore("TELEFONO", v, lambda: EN.finto_tel_en(rng, v))["f"]
                return G.stampo(v, f)
        if t == "TELEFONO" and R.RE_TEL_VERDE.fullmatch(v):  # numero verde: il prefisso resta (800, 199…)
            c = re.sub(r"\D", "", v)
            return G.stampo(v, self._valore("TELEFONO", v, lambda: c[:3] + G.cifre_casuali(rng, len(c) - 3))["f"])
        if t == "TELEFONO":
            naz = canon("TELEFONO", v)
            f = self._valore("TELEFONO", v, lambda: G.finto_telefono(rng, naz))["f"]
            cifre = re.sub(r"\D", "", v)
            return G.stampo(v, cifre[: len(cifre) - len(naz)] + f)
        if t == "EMAIL":
            return self._finto_email(v)
        if t == "URL":
            return self._finto_url(v)
        if t == "IP":
            return self._valore("IP", v, lambda: G.finto_ip(rng))["f"]
        if t == "TARGA":
            if not R.RE_TARGA.fullmatch(v):  # targhe estere (UK «AB12 CDE», US «7MBD219»): stessa struttura
                return G.stampo(v, self._valore("TARGA", v, lambda: canon("TARGA", G.come_classi(rng, v)))["f"])
            return G.stampo(v, self._valore("TARGA", v, lambda: G.finta_targa(rng))["f"])
        if t == "CODICE":
            return G.stampo(v, self._valore("CODICE", v, lambda: canon("CODICE", G.finto_documento(rng, v)))["f"])
        if t == "DOCUMENTO":
            return G.stampo(v, self._valore("DOCUMENTO", v, lambda: canon("DOCUMENTO", G.finto_documento(rng, v)))["f"])
        if t == "PRATICA":
            return self._valore("PRATICA", v, lambda: G.finta_pratica(rng, v, self.delta_anni))["f"]
        if t == "CAP" and (not re.fullmatch(r"\d{5}", v) or (self._lingua == "en" and not self._uk)):
            return self._valore("CAP", v, lambda: EN.finto_cap_en(rng, v, self._uk))["f"]
        if t == "CAP":
            return self._valore("CAP", v, lambda: rng.choice(dati.COMUNI)[2][:3] + G.cifre_casuali(rng, 2))["f"]
        if t == "NUMERO":
            return self._valore("NUMERO", v, lambda: G.finto_numero(rng, v))["f"]
        if t == "INDIRIZZO":
            m = s.meta
            pool = DE.ALIAS_STREETS if m.get("en") else dati.ALIAS_VIE
            liberi = [x.strip() for x in pool if norm(x.strip()) not in self._testo_norm] or [x.strip() for x in pool]
            via_v = self._valore("VIA", m["via"], lambda: rng.choice(liberi))
            if m.get("en") and not via_v.get("en"):
                via_v["en"] = True  # «123 Coral Reef Drive»: il civico sta prima della via
                self._toccata()
            via_f = self._forma_finta(via_v, m["via"], via_v["f"], False)
            if m["via"][:1].isupper() and via_f[:1].islower() and m["pref"] in ("Via", "Viale", "Piazza", "Corso", "Largo", "Vicolo", "Strada", "Piazzale"):
                pass
            if "civ" in m and m["civ_inizio"] < m["via_inizio"]:  # inglese: «940 Coral Reef Drive»
                civ_f = self._civico(via_f, m["civ"])
                return "".join([testo[s.inizio:m["civ_inizio"]], civ_f, testo[m["civ_fine"]:m["via_inizio"]], via_f,
                                testo[m["via_fine"]:s.fine]])
            pezzi = [testo[s.inizio:m["via_inizio"]], via_f]
            if "civ" in m:
                civ_f = self._civico(via_f, m["civ"])
                pezzi += [testo[m["via_fine"]:m["civ_inizio"]], civ_f, testo[m["civ_fine"]:s.fine]]
            else:
                pezzi.append(testo[m["via_fine"]:s.fine])
            return "".join(pezzi)
        if t == "CAP_CITTA":
            cap = s.testo[:5]
            nome = s.meta["citta"]
            cv = self._citta(nome)
            cap_f = self._cap_finto(cv, cap)
            i_citta = s.testo.index(nome, 5)
            resto = s.testo[i_citta + len(nome):]
            if re.search(r"\([A-Z]{2}\)", resto):
                resto = re.sub(r"\([A-Z]{2}\)", f"({cv['fs']})", resto)
            return cap_f + s.testo[5:i_citta] + self._forma_finta(cv, nome, cv["f"], False) + resto
        if t == "CITTA" and s.meta.get("stato"):  # «Sacramento, CA» → «Tulsa, OK»
            cv = self._citta(s.meta["citta"])
            st = cv.get("fs") or s.meta["stato"]
            if cv.get("fs"):
                cv.setdefault("rs", s.meta["stato"])
                if len(s.meta["stato"]) > 2:  # «Portland, Oregon» → «Tulsa, Oklahoma»
                    st = DE.US_STATES.get(cv["fs"], st)
                cv.setdefault("stati", {})[st] = s.meta["stato"]
            return self._forma_finta(cv, s.meta["citta"], cv["f"], False) + v[len(s.meta["citta"]):-len(s.meta["stato"])] + st
        if t == "CITTA":
            nome = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", v)
            cv = self._citta(nome)
            resto = v[len(nome):]
            if resto:
                resto = re.sub(r"\([A-Z]{2}\)", f"({cv['fs']})", resto)
            return self._forma_finta(cv, nome, cv["f"], False) + resto
        if t == "AZIENDA":
            nome = s.meta["nome"]
            av = self._valore("AZIENDA", nome, lambda: rng.choice(dati.ALIAS_AZIENDE))
            return applica_caso(nome, av["f"]) + testo[s.meta["nome_fine"]:s.fine]
        if t == "SANITARIO":
            if self.config.sanitari == "sostituisci":
                return applica_caso(v, self._valore("SANITARIO", v, lambda: rng.choice(
                    [p for p in dati.PATOLOGIE if norm(p) != norm(v)]))["f"])
            return None
        return None

    def _civico(self, via_finta: str, civ_reale: str) -> str:
        for k, r in self.civici.items():
            if k.startswith(norm(via_finta) + "|") and r == civ_reale:
                return k.split("|", 1)[1]
        for _ in range(100):
            c = G.finto_civico(self._rng, civ_reale)
            if f"{norm(via_finta)}|{c}" not in self.civici and c != civ_reale:
                break
        self.civici[f"{norm(via_finta)}|{c}"] = civ_reale
        self._toccata()
        return c

    def _finto_url(self, url: str) -> str:
        m = re.match(r"(https?://)([^/:?#]+)(.*)", url, re.I)
        if not m:
            return url
        host = m.group(2)
        chiave_dom = f"DOMINIO|{canon('DOMINIO', '.'.join(host.lower().split('.')[-2:]))}"
        nuovo_host = host
        if chiave_dom in self.valori or self.config.modalita == "fuga" or self._sostituisci_in_minuscolo(host) != host:
            if host.lower() not in dati.DOMINI_PUBBLICI and not re.search(r"(?:^|\.)(?:google|linkedin|facebook|instagram|youtube|wikipedia|gov|europa|agenziaentrate|inps)\.", host.lower()):
                nuovo_host = self._finto_dominio(host)
        resto = self._sostituisci_in_minuscolo(m.group(3))
        resto = re.sub(r"\d{5,}", lambda x: G.cifre_casuali(self._rng, len(x.group(0))), resto)
        return m.group(1) + nuovo_host + resto

    # ------------------------------------------------------------------ occorrenze note
    def _regex_noti(self):
        if self._cache_noti is not None:
            return self._cache_noti
        voci = []
        for n, u in self.unita.items():
            voci.append((u["r"], "NOME" if u["ruolo"] == "nome" else "COGNOME", n))
        for k, v in self.valori.items():
            tipo = k.split("|", 1)[0]
            if tipo in ("CITTA", "VIA", "AZIENDA", "PRATICA", "DOCUMENTO", "CODICE", "EMAIL", "NUMERO", "TARGA", "SANITARIO", "CAP") + TIPI_EN:
                if len(v["r"]) >= 3 and not (tipo in TIPI_EN + ("CODICE",) and len(canon(tipo, v["r"])) < 5):
                    voci.append((v["r"], tipo, k))
        voci.sort(key=lambda x: -len(x[0]))
        if not voci:
            self._cache_noti = (None, {})
            return self._cache_noti
        indice = {}
        parti = []
        for i, (sup, tipo, k) in enumerate(voci):
            pat = r"\s+".join(re.escape(w) for w in sup.split())
            parti.append((sup[:1], False, f"(?P<g{i}>{pat})"))
            indice[f"g{i}"] = (tipo, k)
        rx = re.compile(r"(?<![\w@.])(?:" + _alternanza(parti) + r")(?![\w])", re.I)
        self._cache_noti = (rx, indice)
        return self._cache_noti

    def _occorrenze_note(self, testo: str) -> list:
        rx, indice = self._regex_noti()
        out = []
        if rx is None:
            return out
        for m in rx.finditer(testo):
            tipo, k = indice[m.lastgroup]
            w = m.group(0)
            if tipo in ("NOME", "COGNOME", "CITTA", "VIA", "AZIENDA") and w.islower():
                if not (tipo in ("NOME", "COGNOME") and self.unita[k].get("min")):
                    continue
            if (tipo in ("PRATICA", "DOCUMENTO", "CODICE", "NUMERO", "TARGA", "CAP") + TIPI_EN
                    and (testo[m.start() - 1:m.start()] in ("/", "-", ".") and m.start() > 0
                         or re.match(r"[/\-.]\w", testo[m.end():m.end() + 2]))):
                continue  # «07/2025» (pratica) dentro la data «01/07/2025»
            prec = R._precedente(testo, m.start()) if tipo in ("NOME", "COGNOME") else ""
            if prec in _SANTI and self.config.modalita != "fuga" and not (prec == "s." and tipo == "COGNOME"):  # «S. Rossi» è un'iniziale
                continue
            if tipo in ("NOME", "COGNOME"):
                nuovo = self._forma_finta(self.unita[k], w, self.unita[k]["f"], True)
                out.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": nuovo}))
            elif tipo == "CITTA":
                out.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": self._forma_finta(self.valori[k], w, self.valori[k]["f"], False)}))
            elif tipo == "SANITARIO" and self.config.sanitari != "sostituisci":
                continue
            elif tipo in ("PRATICA", "DOCUMENTO", "CODICE", "NUMERO", "TARGA", "CAP") + TIPI_EN:
                f = self.valori[k]["f"]
                out.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": G.stampo(w, canon(tipo, f)) if tipo != "PRATICA" else f}))
            else:
                out.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": applica_caso(w, self.valori[k]["f"])}))
        # Iniziali: «M. Rossi», «Rossi M.»
        cognomi = {n: u for n, u in self.unita.items() if u["ruolo"] == "cognome"}
        if cognomi:
            alt = "|".join(r"\s+".join(re.escape(w) for w in u["r"].split()) for u in sorted(cognomi.values(), key=lambda u: -len(u["r"])))
            for m in re.finditer(rf"(?<![\w.])([A-Z])\.\s?(?=(?:{alt})(?![\w]))", testo, re.I):
                cg = re.match(rf"(?:{alt})", testo[m.end():], re.I).group(0)
                ini = self._iniziale(m.group(1), cg)
                if ini:
                    out.append(R.Span(m.start(1), m.end(1), "INIZIALE", m.group(1), 1.0, {"nuovo": ini}))
            for m in re.finditer(rf"(?<![\w])(?:{alt})\s([A-Z])\.(?![\w])", testo, re.I):
                cg = testo[m.start():m.start(1) - 1]
                ini = self._iniziale(m.group(1), cg)
                if ini:
                    out.append(R.Span(m.start(1), m.end(1), "INIZIALE", m.group(1), 1.0, {"nuovo": ini}))
        return out

    def _iniziale(self, lettera: str, cognome_reale: str) -> str | None:
        """Iniziale finta per «M. Rossi»: una corrispondenza lettera↔lettera per famiglia, sempre reversibile.
        Se nessuna persona nota ha quell'iniziale, si sceglie comunque una lettera libera della famiglia."""
        cg = re.sub(r"\s+", " ", norm(cognome_reale))
        L = lettera.upper()
        chiave = f"{cg}|{L}"
        if chiave not in self.iniziali:
            usate = {v for k, v in self.iniziali.items() if k.startswith(cg + "|")}
            libere = [c for c in "ABCDEFGILMNOPRSTV" if c not in usate and c != L] or [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in usate]
            if not libere:
                return None
            self.iniziali[chiave] = self._rng.choice(libere)
            self._toccata()
        f = self.iniziali[chiave]
        return f if lettera.isupper() else f.lower()

    def _finti_presenti(self, testo: str) -> list:
        """Alias della sessione che compaiono, maiuscoli, nel testo originale."""
        trovati = []
        for nf in self.unita_finte:
            u = self.unita[self.unita_finte[nf]]
            if re.search(rf"(?<![\w]){re.escape(u['f'])}(?![\w])", testo):
                trovati.append(u["f"])
        return trovati

    def controlla_fughe(self, originale: str, uscita: str, rilevati: list | None = None) -> list:
        """Tipi dei dati originali (noti alla sessione o appena rilevati) ancora presenti nel testo d'uscita."""
        fughe = []
        piatto = re.sub(r"[\s\-.]", "", uscita).upper()
        for tipo, val in rilevati or []:
            c = re.sub(r"[\s\-.]", "", val).upper()
            if len(c) >= 6 and c in piatto:
                fughe.append(tipo)
        for k, v in self.valori.items():
            tipo, c = k.split("|", 1)
            if tipo in ("CF", "IBAN", "CARTA", "PIVA") and len(c) >= 8 and c.upper() in re.sub(r"[\s\-.]", "", originale).upper():
                if c.upper() in piatto:
                    fughe.append(tipo)
            elif tipo == "EMAIL" and v["r"].lower() in originale.lower() and v["r"].lower() in uscita.lower():
                fughe.append(tipo)
            elif tipo == "TELEFONO" and len(c) >= 8 and c in re.sub(r"\D", "", originale) and c in re.sub(r"\D", "", uscita):
                fughe.append(tipo)
        for n, u in self.unita.items():
            pat = rf"(?<![\w]){r'\s+'.join(re.escape(w) for w in u['r'].split())}(?![\w])"
            for m in re.finditer(pat, uscita, re.I):
                if m.group(0).islower() or R._precedente(uscita, m.start()) in _SANTI:
                    continue
                if re.search(pat, originale, re.I):
                    fughe.append("PERSONA")
                    break
        return fughe

    # ------------------------------------------------------------------ ripristino
    def _regex_finti(self):
        if self._cache_finti is not None:
            return self._cache_finti
        voci = []
        for nf, nr in self.unita_finte.items():
            u = self.unita[nr]
            voci.append((u["f"], "UNITA", nr))
        for k, v in self.valori.items():
            tipo = k.split("|", 1)[0]
            if tipo in ("CITTA", "VIA", "AZIENDA", "EMAIL", "DOMINIO", "PRATICA", "SANITARIO", "NUMERO", "IP", "CAP", "DOCUMENTO", "CODICE", "TARGA") + TIPI_EN:
                if tipo in TIPI_EN + ("CODICE",) and len(canon(tipo, v["f"])) < 5:
                    continue  # numeri corti (foglio 12, lotto 7): solo con il loro contesto, non ovunque
                voci.append((v["f"], tipo, k))
        voci.sort(key=lambda x: -len(x[0]))
        if not voci:
            self._cache_finti = (None, {})
            return self._cache_finti
        indice, parti = {}, []
        for i, (sup, tipo, k) in enumerate(voci):
            pat = r"\s+".join(re.escape(w) for w in sup.split())
            if tipo in ("DOCUMENTO", "CODICE", "TARGA") + TIPI_EN:  # il modello può rimettere o togliere spazi e trattini
                pat = r"[\s\-./]?".join(re.escape(c) for c in sup)
            if tipo == "VIA" and self.valori[k].get("en"):
                pat = r"(?:(?P<pc{0}>\d{{1,6}}[A-Za-z]?)[ \t]+(?:(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?[ \t]+)?)?".format(i) + pat
            if tipo == "VIA":
                pat += r"(?:(?P<sc{0}>,?\s*(?:n\.\s?|n°\s?|nr\.?\s?|civ\.?\s?)?)(?P<cv{0}>\d{{1,4}}(?:\s?/\s?[A-Za-z0-9]{{1,3}}|[A-Za-z](?![A-Za-z]))?))?".format(i)
            if tipo == "CITTA":
                pat = r"(?:(?P<cp{0}>\d{{5}})[ \t]*[-–]?[ \t]*)?".format(i) + f"(?P<nm{i}>{pat})" + (r"(?:[ \t]*\((?P<pv{0}>[A-Z]{{2}})\)|,?[ \t]+(?P<st{0}>[A-Z]{{2}}|" + _NOMI_STATI + r")(?![\w]))?").format(i)
            parti.append((sup[:1], tipo == "CITTA" or (tipo == "VIA" and bool(self.valori[k].get("en"))), f"(?P<g{i}>{pat})"))
            indice[f"g{i}"] = (tipo, k, i)
        rx = re.compile(r"(?<![\w])(?:" + _alternanza(parti) + r")(?![\w])", re.I)
        self._cache_finti = (rx, indice)
        return self._cache_finti

    def ripristina(self, testo: str, contesto_anno: int | None = None, controllo: bool = False) -> Esito:
        self._controlla_scadenza()
        spans: list[R.Span] = []
        incerti: list[dict] = []
        for m in RE_SEGNAPOSTO.finditer(testo):
            if m.group(0) in self.segnaposti:
                spans.append(R.Span(m.start(), m.end(), "CALCOLO", m.group(0), 1.0, {"nuovo": self.segnaposti[m.group(0)]}))
        # a) schemi con controllo: si normalizza e si cerca il finto
        schemi = R.trova_schemi(testo, "bilanciata", sanitari=False)
        if self.inglese:
            schemi += EN.trova_schemi_en(testo)
        else:
            schemi += EN.trova_telefoni_esteri(testo)
        for s in schemi:
            if s.tipo not in ("CF", "IBAN", "PIVA", "CARTA", "TELEFONO", "TARGA", "DOCUMENTO", "PRATICA", "CODICE") + TIPI_EN:
                continue
            k = self.valori_finti.get(f"{s.tipo}|{canon(s.tipo, s.testo)}")
            if k:
                reale = self.valori[k]["r"]
                if s.tipo == "TELEFONO":
                    naz_r = canon("TELEFONO", reale)
                    cifre = re.sub(r"\D", "", s.testo)
                    nuovo = G.stampo(s.testo, cifre[: len(cifre) - len(naz_r)] + naz_r)
                elif s.tipo == "PIVA":
                    nuovo = (re.match(r"IT\s?", s.testo).group(0) if s.testo.upper().startswith("IT") else "") + canon("PIVA", reale)
                else:
                    nuovo = G.stampo(s.testo, canon(s.tipo, reale)) if s.tipo != "PRATICA" else reale
                spans.append(R.Span(s.inizio, s.fine, s.tipo, s.testo, 1.0, {"nuovo": nuovo}))
            elif not controllo and s.tipo in ("CF", "IBAN", "CARTA", "PIVA", "TELEFONO", "SSN", "NHS", "NINO", "ROUTING"):
                c = canon(s.tipo, s.testo)
                vicini = [kk for kk in self.valori_finti if kk.startswith(s.tipo + "|") and _lev(kk.split("|", 1)[1], c, 2) <= 2]
                if vicini:
                    incerti.append({"testo": s.testo, "inizio": s.inizio, "fine": s.fine,
                                    "motivo": f"{s.tipo} simile a un dato finto ma non identico: non ripristinato"})
        # b) alias e valori finti esatti
        rx, indice = self._regex_finti()
        if rx is not None:
            for m in rx.finditer(testo):
                tipo, k, i = indice[m.lastgroup]
                w = m.group(0)
                if tipo == "UNITA":
                    if w.islower() and not self.unita[k]["f"].islower() and not self.unita[k].get("min"):
                        continue  # «sara'» (verbo) non è l'alias «Sara»
                    spans.append(R.Span(m.start(), m.end(), "NOME", w, 1.0, {"nuovo": self._forma_vera(self.unita[k], w, True)}))
                elif tipo == "VIA":
                    v = self.valori[k]
                    via_txt = w
                    nuovo = None
                    cv = m.group(f"cv{i}")
                    if cv:
                        base_len = m.start(f"sc{i}") - m.start()
                        via_txt = w[:base_len]
                        civ_r = self.civici.get(f"{norm(v['f'])}|{cv}")
                        if civ_r is None:
                            incerti.append({"testo": w, "inizio": m.start(), "fine": m.end(),
                                            "motivo": "numero civico non presente nella mappa: lasciato com'è"})
                            civ_r = cv
                        nuovo = applica_caso(via_txt, v["r"]) + m.group(f"sc{i}") + civ_r
                    else:
                        nuovo = applica_caso(w, v["r"])
                    pc = m.groupdict().get(f"pc{i}")
                    if pc:  # civico prima della via (inglese): due pezzi, così un altro dato sul civico non fa perdere la via
                        civ_r = self.civici.get(f"{norm(v['f'])}|{pc}")
                        if civ_r is None:
                            incerti.append({"testo": w, "inizio": m.start(), "fine": m.end(),
                                            "motivo": "numero civico non presente nella mappa: lasciato com'è"})
                            civ_r = pc
                        resto = w[m.end(f"pc{i}") - m.start():]
                        nome_via = re.match(r"(\s+(?:(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?\s+)?)(.*)", resto, re.S)
                        a_nome = m.end(f"pc{i}") + len(nome_via.group(1))
                        spans.append(R.Span(m.start(f"pc{i}"), m.end(f"pc{i}"), "CIVICO", pc, 1.0, {"nuovo": civ_r}))
                        spans.append(R.Span(a_nome, m.end(), "VIA", testo[a_nome:m.end()], 1.0,
                                            {"nuovo": self._forma_vera(v, nome_via.group(2), False)}))
                        continue
                    if not m.group(f"cv{i}"):
                        nuovo = self._forma_vera(v, w, False)
                    spans.append(R.Span(m.start(), m.end(), "VIA", w, 1.0, {"nuovo": nuovo}))
                elif tipo == "CITTA":
                    v = self.valori[k]
                    cp, pv = m.group(f"cp{i}"), m.group(f"pv{i}")
                    pezzi = []
                    if cp:
                        cap_r = self.cap.get(f"{norm(v['f'])}|{cp}")
                        if cap_r is None:
                            incerti.append({"testo": cp, "inizio": m.start(f"cp{i}"), "fine": m.end(f"cp{i}"),
                                            "motivo": "CAP non presente nella mappa: lasciato com'è"})
                            cap_r = cp
                        pezzi.append((m.start(f"cp{i}"), m.end(f"cp{i}"), cap_r))
                    pezzi.append((m.start(f"nm{i}"), m.end(f"nm{i}"), self._forma_vera(v, m.group(f"nm{i}"), False)))
                    st = m.group(f"st{i}")
                    if st and st in v.get("stati", {}):
                        pezzi.append((m.start(f"st{i}"), m.end(f"st{i}"), v["stati"][st]))
                    elif st and v.get("rs") and st == v.get("fs"):
                        pezzi.append((m.start(f"st{i}"), m.end(f"st{i}"), v["rs"]))
                    if pv:
                        sig_r = v.get("rs") or next((c[1] for c in dati.COMUNI if norm(c[0]) == norm(v["r"])), pv)
                        pezzi.append((m.start(f"pv{i}"), m.end(f"pv{i}"), sig_r))
                    nuovo, cur = [], m.start()
                    for a0, b0, t0 in pezzi:
                        nuovo += [testo[cur:a0], t0]
                        cur = b0
                    nuovo.append(testo[cur:m.end()])
                    spans.append(R.Span(m.start(), m.end(), "CITTA", w, 1.0, {"nuovo": "".join(nuovo)}))
                elif tipo == "DOMINIO":
                    spans.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": self.valori[k]["r"].lower()}))
                else:
                    spans.append(R.Span(m.start(), m.end(), tipo, w, 1.0, {"nuovo": applica_caso(w, self.valori[k]["r"])}))
            # Iniziali davanti o dopo un cognome finto
            cognomi_f = {norm(u["f"]): nr for nr, u in self.unita.items() if u["ruolo"] == "cognome"}
            if cognomi_f:
                alt = "|".join(re.escape(self.unita[nr]["f"]) for nr in cognomi_f.values())
                for m in re.finditer(rf"(?<![\w.])([A-Z])\.\s?(?=(?:{alt})(?![\w]))", testo, re.I):
                    cg = re.match(rf"(?:{alt})", testo[m.end():], re.I).group(0)
                    self._iniziale_inversa(m, cg, cognomi_f, spans, incerti)
                for m in re.finditer(rf"(?<![\w])(?:{alt})\s([A-Z])\.(?![\w])", testo, re.I):
                    cg = testo[m.start():m.start(1) - 1]
                    self._iniziale_inversa(m, cg, cognomi_f, spans, incerti)
        # c) calcoli rispetto a oggi chiesti dal modello e annotazioni d'età da togliere
        spans += self._marcatori(testo, incerti)
        # d) date: spostamento inverso dentro la finestra della sessione
        spans += self._date_inverse(testo, incerti, contesto_anno)
        finali = R.arbitra(spans)
        out, cur, sostituzioni, conteggi = [], 0, [], {}
        for s in finali:
            out.append(testo[cur:s.inizio])
            out.append(s.meta["nuovo"])
            cur = s.fine
            sostituzioni.append((s.inizio, s.fine, s.meta["nuovo"], s.tipo))
            conteggi[s.tipo] = conteggi.get(s.tipo, 0) + 1
        out.append(testo[cur:])
        if not controllo:  # il controllo di ritorno guarda solo il testo, non gli avvisi
            incerti += self._sospetti(testo, finali)
        log.info("ripristina sessione=%s ripristinati=%d incerti=%d", self.id, len(finali), len(incerti))
        return Esito("".join(out), sostituzioni, conteggi, [], incerti)

    def _marcatori(self, testo: str, incerti: list) -> list:
        oggi = dt.date.today()
        out = [R.Span(m.start(), m.end(), "CALCOLO", m.group(0), 1.0, {"nuovo": ""}) for m in RE_ANNOTAZIONE_ETA.finditer(testo)]
        for m in RE_MARCATORE.finditer(testo):
            tipo = m.group("tipo").upper().replace("À", "A")
            if tipo == "OGGI":
                out.append(R.Span(m.start(), m.end(), "CALCOLO", m.group(0), 1.0, {"nuovo": oggi.strftime("%d/%m/%Y")}))
                continue
            date = trova_date(m.group("arg") or "", self.oggi_fittizio().year, False)
            if not date or date[0].granularita != "giorno":
                incerti.append({"testo": m.group(0), "inizio": m.start(), "fine": m.end(),
                                "motivo": "calcolo rispetto a oggi senza una data leggibile: lasciato com'è"})
                continue
            vera = date[0].data - dt.timedelta(days=self.delta)
            if tipo == "ETA":
                n = _anni_compiuti(vera, oggi)
                risultato = f"{n} ann{'o' if n == 1 else 'i'}"
            else:
                g = (vera - oggi).days
                if tipo == "GIORNI":
                    risultato = "oggi" if g == 0 else (f"tra {g} giorn{'o' if g == 1 else 'i'}" if g > 0 else f"{-g} giorn{'o' if g == -1 else 'i'} fa")
                else:
                    risultato = ("scade oggi" if g == 0 else f"non ancora scaduto (mancano {g} giorn{'o' if g == 1 else 'i'})"
                                 if g > 0 else f"scaduto da {-g} giorn{'o' if g == -1 else 'i'}")
            out.append(R.Span(m.start(), m.end(), "CALCOLO", m.group(0), 1.0, {"nuovo": risultato}))
        return out

    def _iniziale_inversa(self, m, cognome_finto, cognomi_f, spans, incerti):
        nr = cognomi_f.get(norm(cognome_finto))
        if nr is None:
            return
        inversa = {v: k.split("|", 1)[1] for k, v in self.iniziali.items() if k.startswith(nr + "|")}
        vera = inversa.get(m.group(1).upper())
        if vera:
            spans.append(R.Span(m.start(1), m.end(1), "INIZIALE", m.group(1), 1.0,
                                {"nuovo": vera if m.group(1).isupper() else vera.lower()}))
        else:
            incerti.append({"testo": m.group(0), "inizio": m.start(), "fine": m.end(),
                            "motivo": "iniziale davanti a un cognome finto ma non presente nella mappa: lasciata com'è"})

    def _finestra_date(self) -> tuple[dt.date, dt.date]:
        oggi_f = self.oggi_fittizio()
        estremi = [dt.date.fromisoformat(x) for x in self.date_finte] + [oggi_f]
        marg = dt.timedelta(days=365 * self.config.margine_anni_ripristino)
        return min(estremi) - marg, max(estremi) + marg

    def _date_inverse(self, testo: str, incerti: list, contesto_anno: int | None) -> list:
        if not self.config.date:
            return []
        if self._solo_nascita:  # nessuno spostamento «a finestra»: solo le forme esatte delle date di nascita finte
            out = []
            for d in trova_date(testo, contesto_anno or self.oggi_reale.year, False, self.convenzione):
                if d.testo in self.date_sup:
                    out.append(R.Span(d.inizio, d.fine, "DATA", d.testo, 1.0, {"nuovo": self.date_sup[d.testo]}))
            return out
        lo, hi = self._finestra_date()
        out = []
        for d in trova_date(testo, contesto_anno or self.oggi_fittizio().year, self.config.anni_contesto, self.convenzione):
            if d.normativa:
                continue
            if d.granularita == "anno":
                if not (lo.year <= d.data.year <= hi.year):
                    continue
            elif not (lo <= d.data <= hi):
                if d.granularita in ("giorno", "mese"):
                    incerti.append({"testo": d.testo, "inizio": d.inizio, "fine": d.fine,
                                    "motivo": "data fuori dalla finestra della sessione: lasciata com'è"})
                continue
            if d.data.isoformat() in self.date_ferme and d.granularita == "giorno":
                continue
            if d.granularita == "mese":
                d = self._mese_inverso(d)
            nuovo = self.date_sup.get(d.testo)
            if nuovo is None or (d.testo not in self.date_fidate and d.granularita != "giorno_senza_anno"
                                 and not d.speciale.get("tipo") and not self._stessa_data(nuovo, d, -self.delta)):
                nuovo = sposta(d, testo, -self.delta, self._lingua != "it")
            out.append(R.Span(d.inizio, d.fine, "DATA", d.testo, 1.0, {"nuovo": nuovo}))
        return out

    def _mese_inverso(self, d):
        """Il mese vero è quello che, spostato in avanti, dà il mese finto (il calcolo diretto può sbagliare di uno)."""
        import copy
        for k in (0, -1, 1):
            base = d.data - dt.timedelta(days=self.delta)
            y, m = base.year, base.month + k
            y, m = (y + (m - 1) // 12, (m - 1) % 12 + 1)
            cand = dt.date(y, m, 15)
            avanti = cand + dt.timedelta(days=self.delta)
            if (avanti.year, avanti.month) == (d.data.year, d.data.month):
                d2 = copy.copy(d)
                d2.data = cand + dt.timedelta(days=self.delta)
                return d2
        return d

    def _stessa_data(self, originale: str, d, delta: int) -> bool:
        """La forma originale salvata indica la stessa data del calcolo inverso? (evita di riusarla a sproposito)"""
        attesa = d.data + dt.timedelta(days=delta)
        trovate = trova_date(originale, attesa.year, self.config.anni_contesto, self.convenzione)
        if len(trovate) != 1 or trovate[0].granularita != d.granularita:
            return False
        t = trovate[0].data
        if d.granularita == "giorno":
            return t == attesa
        if d.granularita == "giorno_senza_anno":
            return (t.month, t.day) == (attesa.month, attesa.day)
        if d.granularita == "mese":
            return (t.year, t.month) == ((attesa.replace(day=15)).year, attesa.month)
        return t.year == attesa.year

    def _sospetti(self, testo: str, finali: list) -> list:
        """Parole simili a un alias ma non identiche (alias riscritti o storpiati dal modello)."""
        coperti = [(s.inizio, s.fine) for s in finali]
        alias = {norm(u["f"]) for u in self.unita.values() if len(u["f"]) >= 5}
        alias |= {norm(v["f"]) for k, v in self.valori.items() if k.startswith(("CITTA|", "AZIENDA|")) and len(v["f"]) >= 5}
        out = []
        per_lung: dict = {}
        for a in alias:
            per_lung.setdefault(len(a), []).append(a)
        occ = Intervalli()
        for a, b in coperti:
            occ.aggiungi(a, b)
        visti: dict = {}
        for m in re.finditer(r"(?<![\w])[A-ZÀ-Ý][\w'’]{3,}(?![\w])", testo):
            if not occ.libero(m.start(), m.start() + 1):
                continue
            w = norm(m.group(0))
            if w in alias or w in self.unita:
                continue
            if w in visti and not visti[w]:
                continue
            vicini = [a for n in range(len(w) - 2, len(w) + 2) for a in per_lung.get(n, ())]
            visti[w] = False
            for a in vicini:
                if (w.startswith(a) and len(w) - len(a) <= 2) or _lev(w, a, 1) <= 1:
                    visti[w] = True
                    out.append({"testo": m.group(0), "inizio": m.start(), "fine": m.end(),
                                "motivo": "parola simile a un alias: forse riscritta dal modello, non ripristinata"})
                    break
        return out

    def flusso(self, trattieni: int | None = None) -> "RipristinoFlusso":
        return RipristinoFlusso(self, trattieni)

    def lunghezza_massima_finto(self) -> int:
        l = [len(u["f"]) for u in self.unita.values()] + [len(v["f"]) for v in self.valori.values()]
        return max(l or [20])

    # ------------------------------------------------------------------ sostituzione dei soli valori noti
    def sostituisci_noti(self, testo: str) -> str:
        """Solo i valori già in mappa (per formule, nomi di fogli, metadati brevi)."""
        out, cur = [], 0
        for s in R.arbitra(self._occorrenze_note(testo)):
            out += [testo[cur:s.inizio], s.meta["nuovo"]]
            cur = s.fine
        out.append(testo[cur:])
        return "".join(out)

    # ------------------------------------------------------------------ persistenza
    def a_dizionario(self) -> dict:
        return {"versione": 1, "id": self.id, "creata": self.creata, "scadenza": self.scadenza, "delta": self.delta,
                "oggi_reale": self.oggi_reale.isoformat(), "config": asdict(self.config), "unita": self.unita,
                "persone": self.persone, "valori": self.valori, "civici": self.civici, "cap": self.cap,
                "date_ferme": sorted(self.date_ferme), "date_finte": self.date_finte,
                "date_sup": self.date_sup, "date_fidate": sorted(self.date_fidate), "segnaposti": self.segnaposti, "iniziali": self.iniziali, "convenzione": self.convenzione, "inglese": self.inglese, "lingua": self._lingua}

    @classmethod
    def da_dizionario(cls, d: dict, ner=None) -> "Sessione":
        s = cls(Configurazione(**d["config"]), d["id"], ner, dt.date.fromisoformat(d["oggi_reale"]))
        s.creata, s.scadenza, s.delta = d["creata"], d["scadenza"], d["delta"]
        s.unita, s.persone, s.valori = d["unita"], d["persone"], d["valori"]
        s.civici, s.cap = d["civici"], d["cap"]
        s.date_ferme, s.date_finte = set(d["date_ferme"]), d["date_finte"]
        s.date_sup = d.get("date_sup", {})
        s.date_fidate = set(d.get("date_fidate", []))
        s.segnaposti = d.get("segnaposti", {})
        s._n_segnaposto = len(s.segnaposti) + 1000
        s.iniziali = d.get("iniziali", {})
        s.convenzione = d.get("convenzione", "DMY")
        s.inglese = d.get("inglese", False)
        s._lingua = d.get("lingua", "it")
        s.unita_finte = {norm(u["f"]): n for n, u in s.unita.items()}
        s.valori_finti = {f"{k.split('|', 1)[0]}|{canon(k.split('|', 1)[0], v['f'])}": k for k, v in s.valori.items()}
        s._toccata()
        return s

    def riepilogo(self) -> dict:
        """Solo conteggi: si può registrare senza rivelare nulla."""
        tipi = {}
        for k in self.valori:
            t = k.split("|", 1)[0]
            tipi[t] = tipi.get(t, 0) + 1
        return {"id": self.id, "scadenza": self.scadenza, "persone": len(self.persone),
                "unita_nome": len(self.unita), "valori": tipi, "spostamento_giorni": self.delta}


_RE_RELATIVA_FLUSSO = re.compile(r"(?i)\b(?:u\.\s?s\.|corr\.|p\.\s?v\.|ieri|domani|scors|prossim|last|next|yesterday|"
                                 r"tomorrow|ago|fa\b|\d+(?:st|nd|rd|th)\b|inst\.)")


class RipristinoFlusso:
    """Ripristino a pezzi per le risposte in streaming. Trattiene solo ciò che potrebbe ancora diventare un dato finto:
    l'ultima parola se è l'inizio di un alias o di un valore finto (anche di più parole: «Reggio Em…»), un numero o
    un'email in corso, un marcatore ⟦…⟧ aperto, un'iniziale «L.». Tutto il resto esce subito.
    Con le date «tutte» si tengono in più le ultime due parole (date e anni scritti in più pezzi)."""

    RE_PAROLA = re.compile(r"[\w@+'’./()-]+$")  # con le parentesi: «(72» e «(720)» aspettano il resto del telefono

    def __init__(self, sessione: Sessione, trattieni: int | None = None):
        self.s = sessione
        self.buf = ""
        self.uscito = 0
        self.testa = ""  # primi 1.000 caratteri usciti (forma finta): la data del documento
        self.ctx = ""  # coda del testo già uscito (forma finta): il contesto a sinistra («legge … n. 162») resta visibile
        self.incerti: list = []
        self.ripristinati = 0
        self._anno = None
        self._sup = None
        self._ver = None

    def _superfici(self) -> list:
        if self._sup is None or self._ver != self.s._versione:
            sup = {u["f"].lower() for u in self.s.unita.values()}
            sup |= {str(v["f"]).lower() for v in self.s.valori.values()}
            sup |= {k.lower() for k in self.s.date_sup}
            self._sup = sorted(x for x in sup if x)
            self._ver = self.s._versione
        return self._sup

    def _inizio_coda(self) -> int:
        b = self.buf
        n = len(b)
        if not b:
            return 0
        inizio = n - (len(b) - len(b.rstrip()))  # gli spazi finali aspettano: «1981 [età 44 anni]» si toglie con lo spazio
        aperto = max(b.rfind("⟦"), b.rfind("["))
        if aperto >= 0 and b.find("⟧" if b[aperto] == "⟦" else "]", aperto) < 0 and n - aperto < 40:
            inizio = min(inizio, aperto - (1 if aperto > 0 and b[aperto - 1] == " " else 0))
        sup = self._superfici()
        m = self.RE_PAROLA.search(b.rstrip())
        if m:
            w = m.group(0).lower()
            if re.search(r"[\d\@]", w) or re.fullmatch(r"[a-zà-ý]\.?", w) or any(x.startswith(w.lstrip("('\"«")) for x in sup):
                inizio = min(inizio, m.start())
        # alias di più parole e iniziali («Reggio Em», «L. Galim», «De Galim»), numeri e codici a gruppi («IT60 X054 28»)
        for k in range(1, 9):
            mm = re.search(r"(?:\S+\s+){%d}\S*$" % k, b[-200:])
            if not mm:
                break
            pos = n - len(mm.group(0))
            coda = re.sub(r"\s+", " ", b[pos:].lower()).strip()
            if (any(x.startswith(coda) for x in sup) or re.fullmatch(r"[\d ()./+-]*\d[\d ()./+-]*", coda)
                    or re.fullmatch(r"(?:[a-z0-9]{2,6} )+[a-z0-9]*", coda) and re.search(r"\d", coda)
                    or re.fullmatch(r"[a-zà-ý]\. ?\S*", coda)):
                inizio = min(inizio, pos)
        if self.s.config.date and not self.s._solo_nascita:  # date e anni scritti in più pezzi
            mm = re.search(r"(?:\S+\s+){0,2}\S*\s*$", b[-120:])
            if mm:
                inizio = min(inizio, n - len(mm.group(0)))
        # «Mantova, M…»: dopo una città finta può arrivare la sigla dello stato o della provincia, che torna con lei
        coda80 = b[-80:]
        mc = re.search(r"((?:[^\s,]+ ){0,2}[^\s,]+)(?:,[ \t]*[A-Z]{0,2}|[ \t]*\(?[A-Z]{0,2})$", coda80)
        if mc and mc.group(1).lower() in sup:
            inizio = min(inizio, n - len(coda80) + mc.start(1))
        if inizio < n:  # «940 Coral…»: il civico prima della via (inglese) aspetta insieme alla via
            mc = re.search(r"\d{1,6}[A-Za-z]?[ \t]+(?:(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?[ \t]+)?$", b[:inizio])
            if mc:
                inizio = mc.start()
        # margine fisso: si trattiene sempre la coda lunga quanto il dato finto più lungo (+20), tagliata a uno spazio.
        # Così un dato non esce mai a metà, qualunque sia la forma dei pezzi in arrivo.
        margine = self._margine()
        if n - margine < inizio:
            limite = max(0, n - margine)
            sp = b.rfind(" ", 0, limite + 1)
            sp2 = b.rfind("\n", 0, limite + 1)
            inizio = max(sp, sp2, 0) if max(sp, sp2) > 0 else 0
        return inizio

    def _margine(self) -> int:
        if getattr(self, "_marg_ver", None) != self.s._versione:
            self._marg = min(160, max(40, self.s.lunghezza_massima_finto() + 20))
            self._marg_ver = self.s._versione
        return self._marg

    def scrivi(self, pezzo: str) -> str:
        self.buf += pezzo or ""
        taglio = self._inizio_coda()
        if taglio <= 0:
            return ""
        sost, incerti = self._ripristina_con_contesto()
        for a, b, _, _ in sost:
            if a < taglio < b:
                taglio = a
        if taglio <= 0:
            return ""
        out, cur = [], 0
        for a, b, n, _ in sost:
            if b <= taglio:
                out += [self.buf[cur:a], n]
                cur = b
                self.ripristinati += 1
        out.append(self.buf[cur:taglio])
        self.incerti += [x for x in incerti if x["fine"] <= taglio]
        if len(self.testa) < 1000:
            self.testa = (self.testa + self.buf[:taglio])[:1000]
        self.uscito += taglio
        self.ctx = (self.ctx + self.buf[:taglio])[-160:]
        self.buf = self.buf[taglio:]
        return "".join(out)

    def _ripristina_con_contesto(self) -> tuple[list, list]:
        """Ripristino del buffer con davanti la coda già uscita; si tengono solo le sostituzioni dentro il buffer."""
        # davanti: l'inizio della risposta (data del documento, per «il 3 u.s.») e la coda già uscita
        if self.uscito <= len(self.testa):
            prima = self.testa
        elif _RE_RELATIVA_FLUSSO.search(self.buf):  # la testa serve solo alle date relative
            prima = self.testa + "\n\n" + self.ctx
        else:
            prima = self.ctx
        L = len(prima)
        es = self.s.ripristina(prima + self.buf, self._anno)
        sost = [(a - L, b - L, n, t) for a, b, n, t in es.sostituzioni if a >= L]
        if L and any(a < L < b for a, b, _, _ in es.sostituzioni):
            # un riconoscimento a cavallo del contesto (es. una data già uscita attaccata a un numero) può coprire un dato
            # del buffer: si aggiunge il ripristino del solo buffer dove il primo non ha sostituito nulla
            occ = Intervalli()
            for x, y, _, _ in sost:
                occ.aggiungi(x, y)
            for x, y, n, t in self.s.ripristina(self.buf, self._anno).sostituzioni:
                if occ.libero(x, y):
                    occ.aggiungi(x, y)
                    sost.append((x, y, n, t))
            sost.sort()
        incerti = []
        for x in es.incerti:
            if x["inizio"] >= L:
                y = dict(x)
                y["inizio"], y["fine"] = x["inizio"] - L, x["fine"] - L
                incerti.append(y)
        return sost, incerti

    def chiudi(self) -> str:
        if not self.buf:
            return ""
        sost, incerti = self._ripristina_con_contesto()
        out, cur = [], 0
        for a, b, n, _ in sost:
            out += [self.buf[cur:a], n]
            cur = b
        out.append(self.buf[cur:])
        self.ripristinati += len(sost)
        self.incerti += incerti
        self.ctx = (self.ctx + self.buf)[-160:]
        self.buf = ""
        return "".join(out)
