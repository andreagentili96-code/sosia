"""Prefiltro velocissimo (obiettivo < 20 ms anche su testi lunghi): dice se un testo può contenere dati personali
e se serve il modello NER. Non sostituisce nulla.

- «pulito»: nessun numero lungo, nessuna email o URL, nessuna parola maiuscola fuori dal lessico comune → il testo
  passa così com'è (né regole né modello);
- «ignote»: parole maiuscole che non sono nel lessico né nei dizionari (nomi rari, soprannomi, paesi piccoli):
  solo queste giustificano il modello NER sui messaggi brevi; il modello lavora sulle sole frasi che le contengono.
"""
from __future__ import annotations

import re

from . import dati
from .dati import norm

_COMUNI_IT = """a ad al alla alle allo agli ai anche ancora avere aveva abbiamo hai ha ho hanno anno anni altro altra altri
altre allora andare appena avanti basta bene bello bella buono buona buongiorno buonasera buonanotte ciao come con
contro cosa cose così cui da dal dalla dalle dagli dai davvero del della delle dello degli dei dentro di dice dire
domani dopo dove dovrei dunque e ed è era erano essere eccomi ecco fa fai fare fatto fino forse fra fuori già giorno
giorni grazie gli il in insomma io la le lei li lo loro lui ma magari mai male meglio meno mentre mi mia mie mio miei
molto molti molta molte nel nella nelle nello negli nei nessuno niente no noi non nostro nostra nulla o oggi ogni
ok okay ora ore oppure perché però per piace più poco poi posso potrei potresti prima proprio può qua quale quali
qualche quando quanto quanti quanta quante quasi quel quella quelle quello quelli questo questa queste questi qui
se sei sembra senza sera si sì sia siamo sono solo sopra sotto sta stai stanno stato stata stesso su sua sue suo
suoi sul sulla sulle sullo sugli sui tanto te ti tra tu tua tue tuo tuoi tutti tutto tutta tutte un una uno uno va
vai vado vero via voglio vorrei vuoi vuole ultimo ultima tempo previsioni piove pioggia sole nuvoloso caldo freddo
settimana mese mattina pomeriggio stasera stanotte ieri adesso subito presto tardi lunedì martedì mercoledì giovedì
venerdì sabato domenica gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre
ricordami ricorda dimmi scrivi leggi manda mandami chiama chiamami cerca trova apri prepara controlla spiegami aiutami
fammi puoi potete sapere sai so vedi guarda senti ascolta allora comunque intanto infatti inoltre quindi perciò
claude assistente telefono messaggio messaggi email posta calendario promemoria appuntamento riunione
lavoro casa famiglia mamma papà figlio figlia moglie marito amico amica dottore medico avvocato banca ufficio scuola
salve perfetto certo esatto giusto sbagliato attenzione importante urgente nota note grazie prego scusa scusami
sentito dimenticato fatto detto visto preso messo chiesto risposto scritto letto mandato ricevuto pagato"""
_COMUNI_EN = """a an the this that these those it its is are was were be been being have has had do does did done
you your yours we our us they them their he she his her him i me my mine not no yes and or but if then else when
while for from to of in on at by with without about as into over under up down out all any each every some many
much more most less few other another such same only also just very too can could should would will shall may might
must need use using used make made get got set run show tell ask answer read write edit create delete update check
note notes example examples important never always please here there what which who whom whose why how where
because before after during until since again once first last next new old good bad true false null none ok
user users assistant tool tools file files code task tasks result results output input message messages system
instructions instruction rules rule skill skills agent agents claude anthropic model json api url http https
everything nothing something anything everyone someone today tomorrow yesterday now"""
LESSICO = {norm(w) for w in (_COMUNI_IT + " " + _COMUNI_EN).split()}

_NOMI = {norm(x) for x in dati.NOMI_M + dati.NOMI_F}
_COGNOMI = {norm(x) for x in dati.COGNOMI}
_COMUNI = {norm(c[0]) for c in dati.COMUNI}
NOTI = _NOMI | _COGNOMI | _COMUNI | dati.LUOGHI_IT  # nomi dei dizionari estesi: restano «ignoti», li guarda il modello

RE_MAIUSCOLA = re.compile(r"(?<![\w'’])[A-ZÀ-Ý][\w'’-]{1,}")
RE_SCHEMA = re.compile(r"\d[\d\s./-]{3,}\d|@|https?://|\b[A-Z]{2}\d{2}[A-Z0-9]{4}|\b[A-Za-z]{6}\d{2}[A-Za-z]\d{2}|\b\d{5}\b|\b[A-Z]{2}\s?\d{3}\s?[A-Z]{2}\b")
# date e numeri che contano anche in minuscolo: mesi, «u.s.», «corr.», trimestri, anni
RE_DATE_MINUSCOLE = re.compile(r"(?i)\b(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|"
                               r"dicembre|january|february|march|april|june|july|august|september|october|november|december|"
                               r"u\.\s?s\.|corr\.|corrente|c\.\s?m\.|p\.\s?v\.|q[1-4]|trimestre|quarter|(?:19|20)\d\d|\d{1,2}/\d{1,2})\b")
RE_INDIRIZZO = re.compile(r"(?i)\b(?:via|viale|piazza|corso|largo|vicolo|località|strada)\s+[A-ZÀ-Ý0-9]")
RE_FRASE = re.compile(r"[^.!?\n]+[.!?\n]?")


def _parole_comuni() -> frozenset:
    """Parole comuni italiane e inglesi (sosia/dizionari), meno tutto ciò che è anche un nome, un cognome o un luogo."""
    from . import dati_en as DE
    righe = dati._righe_diz("parole_comuni_it.txt") + dati._righe_diz("parole_comuni_en.txt")
    nomi = (dati.NOMI_EXTRA_M | dati.NOMI_EXTRA_F | dati.COGNOMI_EXTRA | dati.LUOGHI_IT | DE.LUOGHI_EN | DE.nomi_primi()
            | DE.cognomi() | {norm(x) for x in dati.NOMI_M + dati.NOMI_F + dati.COGNOMI})
    return frozenset(w for w in (norm(r) for r in righe) if w not in nomi)


PAROLE_COMUNI = _parole_comuni()
AMBIGUI = dati.NOMI_PAROLA | dati.COGNOMI_PAROLA  # «Guerra», «Valle», «Rosa»: nomi che sono anche parole; le guarda il modello
RE_MINUSCOLA = re.compile(r"(?<![\w'’-])[a-zà-ÿ][a-zà-ÿ'’-]{2,}")
RE_INIZIO_FRASE = re.compile(r"(?:^|[.!?:;]\s+|\n\s*(?:[-*•>#]\s*|\d+[.)]\s*)?)$")


def parole_minuscole(testo: str) -> set:
    return {m.group(0) for m in RE_MINUSCOLA.finditer(testo)}


def esamina(testo: str, unita_note: set | frozenset = frozenset(), minuscole: set | None = None) -> dict:
    """Esito del prefiltro: {pulito, schemi, maiuscole, ignote, frasi_ignote}.
    `minuscole`: parole scritte in minuscolo nel documento; una parola maiuscola a inizio frase o tutta maiuscola che nel
    documento compare anche in minuscolo («Assist» / «assist», «IMPORTANT» / «important») è una parola comune."""
    schemi = bool(RE_SCHEMA.search(testo)) or bool(RE_INDIRIZZO.search(testo)) or bool(RE_DATE_MINUSCOLE.search(testo))
    maiuscole, ignote = [], []
    for m in RE_MAIUSCOLA.finditer(testo):
        w = m.group(0)
        n = norm(w).strip("-'’")
        if n in LESSICO or n in dati.NON_NOMI:
            if n not in unita_note:
                continue
        if (n not in unita_note and n not in NOTI and (w.isupper() or RE_INIZIO_FRASE.search(testo[max(0, m.start() - 6):m.start()]))
                and (n in PAROLE_COMUNI or (minuscole and w.lower() in minuscole))):
            continue  # «Prefer the…», «IMPORTANT:» a inizio frase: parole comuni
        maiuscole.append((m.start(), m.end()))
        ambiguo = n in AMBIGUI and not RE_INIZIO_FRASE.search(testo[max(0, m.start() - 6):m.start()])
        if (n not in NOTI or ambiguo) and n not in unita_note and not (w.isupper() and len(w) <= 4):
            ignote.append((m.start(), m.end()))
    return {"pulito": not schemi and not maiuscole, "schemi": schemi, "maiuscole": len(maiuscole), "ignote": ignote}


def frasi_con(testo: str, posizioni: list, margine: int = 0) -> list[tuple[int, int]]:
    """Intervalli delle frasi che contengono le posizioni indicate (per far lavorare il modello solo lì)."""
    if not posizioni:
        return []
    out = []
    for m in RE_FRASE.finditer(testo):
        a, b = m.start(), m.end()
        if any(a <= p < b for p, _ in posizioni):
            if margine:  # si allarga fino a confini di parola, per non tagliare nomi a metà
                a = max(0, a - margine)
                while a > 0 and not testo[a - 1].isspace():
                    a -= 1
                b = min(len(testo), b + margine)
                while b < len(testo) and not testo[b].isspace():
                    b += 1
            if out and a <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
    return out
