"""Email (.eml): intestazioni, corpo testo e HTML, allegati testuali, DOCX e XLSX.

In pseudonimizzazione si tolgono le intestazioni tecniche che contengono server, indirizzi IP e firme
(Received, DKIM, ARC, Authentication-Results…): al modello non servono e identificano. Gli allegati che non
si sanno trattare (immagini, PDF scansionati, archivi) vengono tolti e segnalati."""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import email.utils
import re

TECNICHE = re.compile(r"^(?:received|dkim-signature|arc-.*|authentication-results|x-originating-ip|x-ms-.*|"
                      r"x-google-.*|x-gm-.*|received-spf|x-received|return-path|x-mailer|user-agent|x-forefront-.*)$", re.I)
DA_TRASFORMARE = {"from", "to", "cc", "bcc", "reply-to", "sender", "subject", "delivered-to", "message-id",
                  "in-reply-to", "references", "thread-topic", "disposition-notification-to"}


def _data(valore: str, giorni: int) -> str:
    try:
        d = email.utils.parsedate_to_datetime(valore)
    except (TypeError, ValueError):
        return valore
    return email.utils.format_datetime(d + dt.timedelta(days=giorni))


BLOCCO = re.compile(r"<\s*/?\s*(?:p|div|br|li|ul|ol|tr|td|th|table|h[1-6]|blockquote|hr|body|html|head|title)\b", re.I)


def _html(h: str, verso) -> str:
    from ._xml import ridistribuisci
    pezzi = re.split(r"(<[^>]+>)", h)
    gruppi, cur = [], []
    for i, p in enumerate(pezzi):
        if p.startswith("<"):
            if BLOCCO.match(p):
                gruppi.append(cur)
                cur = []
        elif p:
            cur.append(i)
    gruppi.append(cur)
    # Ogni blocco (paragrafo, cella…) si trasforma intero, poi il testo torna nei suoi nodi.
    for idx in gruppi:
        blocchi = [pezzi[i] for i in idx]
        if "".join(blocchi).strip():
            e = verso.testo("".join(blocchi))
            for i, n in zip(idx, ridistribuisci(blocchi, e.sostituzioni)):
                pezzi[i] = n
    for i, p in enumerate(pezzi):
        if p.startswith("<") and ("mailto:" in p or "href" in p):
            pezzi[i] = re.sub(r'((?:mailto:|https?://)[^"\'\s>]+)', lambda m: verso.noti(m.group(1)) if not verso.avanti else verso.stringa(m.group(1)), p)
    return "".join(pezzi)


def elabora(dati: bytes, verso, est: str):
    msg = email.message_from_bytes(dati, policy=email.policy.default)
    giorni = verso.giorni()
    # Prima il corpo (più contesto), poi le intestazioni con i nomi già in mappa.
    rimossi = 0
    for parte in list(msg.walk()):
        if parte.is_multipart():
            continue
        ct = parte.get_content_type()
        nome_file = parte.get_filename()
        try:
            if ct == "text/plain" and not nome_file:
                parte.set_content(verso.stringa(parte.get_content()), subtype="plain", charset="utf-8")
            elif ct == "text/html" and not nome_file:
                parte.set_content(_html(parte.get_content(), verso), subtype="html", charset="utf-8")
            elif nome_file:
                rimossi += _allegato(parte, verso)
        except (LookupError, KeyError) as e:  # codifica sconosciuta
            verso.rapporto.avvisi.append(f"parte dell'email non leggibile ({type(e).__name__})")
    nuove = []
    for chiave, valore in msg.items():
        k = chiave.lower()
        if verso.avanti and TECNICHE.match(k):
            continue
        if k == "date":
            nuove.append((chiave, _data(str(valore), giorni)))
        elif k in DA_TRASFORMARE or k.startswith("x-"):
            nuove.append((chiave, verso.stringa(str(valore))))
        else:
            nuove.append((chiave, valore))
    for chiave in set(msg.keys()):
        del msg[chiave]
    for chiave, valore in nuove:
        msg[chiave] = valore
    if rimossi:
        verso.rapporto.avvisi.append(f"{rimossi} allegati non trattabili tolti dall'email (immagini, PDF scansionati, archivi…)")
    return msg.as_bytes(policy=email.policy.default.clone(linesep="\r\n")), est


def _allegato(parte, verso) -> int:
    from . import ESTENSIONI, elabora_bytes
    nome = parte.get_filename() or ""
    estensione = "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    nuovo_nome = verso.stringa(nome)
    if ESTENSIONI.get(estensione) in ("testo", "json", "docx", "xlsx", "pdf"):
        try:
            nuovi, est2 = elabora_bytes(parte.get_payload(decode=True), estensione, verso)
            nuovo_nome = nuovo_nome.rsplit(".", 1)[0] + est2
            mt, st = parte.get_content_type().split("/")
            parte.set_content(nuovi, maintype=mt, subtype=st, filename=nuovo_nome)
            return 0
        except Exception as e:
            verso.rapporto.avvisi.append(f"allegato non elaborato ({type(e).__name__})")
    if verso.avanti:
        parte.set_content("[allegato rimosso dallo scudo: formato non trattabile]", subtype="plain", charset="utf-8")
        del parte["Content-Disposition"]
        return 1
    return 0
