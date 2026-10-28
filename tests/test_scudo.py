"""Prove unitarie dello scudo (solo dati inventati)."""
from __future__ import annotations

import datetime as dt
import re

import pytest

from sosia import Configurazione, FugaRilevata, Sessione
from sosia import validatori as V
from sosia.date import trova_date


def sessione(**kw):
    return Sessione(Configurazione(seme=11, **kw))


# ------------------------------------------------------------------ validatori
def test_cf_generato_valido_e_decodificabile():
    cf = V.genera_cf("Rossi", "Mario", dt.date(1978, 3, 14), "M", "H501")
    assert cf == "RSSMRA78C14H501" + cf[-1] and V.cf_valido(cf)
    info = V.decodifica_cf(cf)
    assert info["nascita"] == dt.date(1978, 3, 14) and info["sesso"] == "M" and info["comune"] == "H501"


def test_iban_cin_e_controllo():
    cin = V.cin_italiano("03069", "05020", "100000012345")
    bban = cin + "03069" + "05020" + "100000012345"
    assert V.iban_valido("IT" + V.cifre_iban("IT", bban) + bban)


def test_piva_e_luhn():
    p = "0123456" + "058"
    assert V.piva_valida(p + V.controllo_piva(p))
    c = "453201511283036"
    assert V.luhn_valido(c + V.cifra_luhn(c))


# ------------------------------------------------------------------ coerenza delle persone
TESTO = """Il sig. Mario Rossi (C.F. RSSMRA78C14H501W), nato a Roma il 14/03/1978, e la moglie Anna Rossi.
ROSSI MARIO ha firmato; M. Rossi e il sig. Rossi sono la stessa persona. Rossi M. conferma."""


def test_varianti_della_stessa_persona():
    s = sessione()
    e = s.pseudonimizza(TESTO)
    a_m = s.unita["mario"]["f"]
    a_r = s.unita["rossi"]["f"]
    assert f"{a_m} {a_r}" in e.testo
    assert f"{a_r.upper()} {a_m.upper()}" in e.testo
    assert f"{a_m[0]}. {a_r}" in e.testo
    assert f"{a_r} {a_m[0]}." in e.testo
    assert "Rossi" not in e.testo and "Mario" not in e.testo
    # stessa famiglia: stesso cognome finto
    assert f"{s.unita['anna']['f']} {a_r}" in e.testo


def test_genere_coerente():
    s = sessione()
    s.pseudonimizza("La sig.ra Giovanna Bruni e il sig. Pietro Bruni.")
    from sosia import dati
    assert s.unita["giovanna"]["f"] in dati.ALIAS_NOMI_F
    assert s.unita["pietro"]["f"] in dati.ALIAS_NOMI_M


def test_cf_finto_coerente_con_persona_e_date():
    s = sessione()
    e = s.pseudonimizza(TESTO)
    cf_finto = re.search(r"C\.F\. (\w{16})", e.testo).group(1)
    assert V.cf_valido(cf_finto)
    info = V.decodifica_cf(cf_finto)
    assert info["nascita"] == dt.date(1978, 3, 14) + dt.timedelta(days=s.delta)
    assert cf_finto[:3] == V.codice_cognome(s.unita["rossi"]["f"])
    assert cf_finto[3:6] == V.codice_nome(s.unita["mario"]["f"])


def test_andata_e_ritorno_esatto():
    s = sessione()
    e = s.pseudonimizza(TESTO)
    assert s.ripristina(e.testo).testo == TESTO


# ------------------------------------------------------------------ date
def test_linea_temporale_e_giorno_della_settimana():
    t = "Lunedì 12 ottobre 2026 la riunione; il 10/10/2026 la lettera; il 14.10.26 la risposta; nel 2019 il contratto."
    s = sessione()
    e = s.pseudonimizza(t)
    assert s.delta % 7 == 0
    a = trova_date(t)
    b = trova_date(e.testo, 2026 + s.delta // 365)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        if x.granularita == "giorno":
            assert y.data - x.data == dt.timedelta(days=s.delta)
            assert y.data.weekday() == x.data.weekday()
    assert s.ripristina(e.testo).testo == t


def test_riferimenti_normativi_non_spostati():
    t = "Ai sensi della legge 30 giugno 2003 n. 196 e del D.Lgs. 14 marzo 2005 n. 82, il 10/10/2026 si delibera."
    s = sessione()
    e = s.pseudonimizza(t)
    assert "30 giugno 2003" in e.testo and "14 marzo 2005" in e.testo
    assert "10/10/2026" not in e.testo


def test_scadenza_calcolata_dal_modello_torna_giusta():
    s = sessione()
    s.pseudonimizza("La lettera è del 10/10/2026.")
    finta = dt.date(2026, 10, 10) + dt.timedelta(days=s.delta)
    risposta = f"Il termine scade il {(finta + dt.timedelta(days=30)).strftime('%d/%m/%Y')}."
    assert s.ripristina(risposta).testo == "Il termine scade il 09/11/2026."


def test_oggi_non_dichiarato_e_calcoli_locali():
    s = sessione()
    oggi = dt.date.today()
    nascita = oggi.replace(year=oggi.year - 40) - dt.timedelta(days=1)
    scad = oggi + dt.timedelta(days=10)
    t = f"La sig.ra Anna Rossi, nata il {nascita.strftime('%d/%m/%Y')}, deve pagare entro il {scad.strftime('%d/%m/%Y')}."
    e = s.pseudonimizza(t)
    assert "[età 40 anni]" in e.testo and "Non conosci la data di oggi" in s.istruzioni_oggi()
    nf = (nascita + dt.timedelta(days=s.delta)).strftime("%d/%m/%Y")
    sf = (scad + dt.timedelta(days=s.delta)).strftime("%d/%m/%Y")
    r = s.ripristina(f"Ha ⟦ETA:{nf}⟧; oggi è ⟦OGGI⟧; il termine: ⟦SCADENZA:{sf}⟧, cioè ⟦GIORNI:{sf}⟧.").testo
    assert r == f"Ha 40 anni; oggi è {oggi.strftime('%d/%m/%Y')}; il termine: non ancora scaduto (mancano 10 giorni), cioè tra 10 giorni."
    assert s.ripristina(e.testo).testo == t  # l'annotazione d'età sparisce al ritorno


def test_oggi_dichiarato_spostato():
    s = sessione(dichiara_oggi=True)
    assert s.oggi_fittizio(dt.date(2026, 10, 27)) == dt.date(2026, 10, 27) + dt.timedelta(days=s.delta)
    assert "Data di oggi" in s.nota_oggi()


# ------------------------------------------------------------------ ripristino robusto
def test_ripristino_con_riscritture_del_modello():
    s = sessione()
    s.pseudonimizza("Il sig. Mario Rossi, IBAN IT60 X054 2811 1010 0000 0123 456, tel. 347 123 4567.")
    am, ar = s.unita["mario"]["f"], s.unita["rossi"]["f"]
    iban_f = next(v["f"] for k, v in s.valori.items() if k.startswith("IBAN|"))
    tel_f = next(v["f"] for k, v in s.valori.items() if k.startswith("TELEFONO|"))
    risposta = (f"| Nome | IBAN |\n|---|---|\n| {ar.upper()} {am.upper()} | {iban_f} |\n"
                f"Il {am[0]}. {ar} va chiamato al {tel_f}.")
    r = s.ripristina(risposta).testo
    assert "ROSSI MARIO" in r and "M. Rossi" in r
    assert "IT60X0542811101000000123456" in r and "3471234567" in r


def test_alias_storpiato_segnalato_non_indovinato():
    s = sessione()
    s.pseudonimizza("Il sig. Mario Rossi ha firmato.")
    ar = s.unita["rossi"]["f"]
    storpiato = ar[:-1] + "x"
    e = s.ripristina(f"Il sig. {storpiato} ha firmato.")
    assert "Rossi" not in e.testo and e.incerti


def test_flusso_con_alias_spezzati():
    s = sessione()
    s.pseudonimizza("La sig.ra Anna Rossi è nata il 02/11/1981 a Milano.")
    finto = s.pseudonimizza("La sig.ra Anna Rossi è nata il 02/11/1981 a Milano.").testo
    f = s.flusso(trattieni=30)
    out = "".join(f.scrivi(finto[i:i + 3]) for i in range(0, len(finto), 3)) + f.chiudi()
    assert out == "La sig.ra Anna Rossi è nata il 02/11/1981 a Milano."


# ------------------------------------------------------------------ sicurezza
def test_modalita_fuga_sostituisce_di_piu():
    t = "Ricoverata all'ospedale Santa Maria Nuova. La paziente Maria Verdi sta bene."
    bil = sessione()
    assert "Santa Maria Nuova" in bil.pseudonimizza(t).testo
    fuga = sessione(modalita="fuga")
    assert "Maria" not in fuga.pseudonimizza(t).testo


def test_blocco_se_resta_un_dato_originale(monkeypatch):
    s = sessione(modalita="fuga")
    originale = s._sostituto
    monkeypatch.setattr(s, "_sostituto", lambda testo, sp, avv: None if sp.tipo == "CF" else originale(testo, sp, avv))
    with pytest.raises(FugaRilevata):
        s.pseudonimizza("Codice fiscale RSSMRA78C14H501W del sig. Mario Rossi.")


def test_nessun_dato_nei_registri(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="sosia")
    s = sessione()
    s.pseudonimizza(TESTO)
    assert "Rossi" not in caplog.text and "RSSMRA" not in caplog.text


def test_scadenza_della_sessione():
    from sosia import SessioneScaduta
    s = sessione()
    s.scadenza = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat()
    with pytest.raises(SessioneScaduta):
        s.pseudonimizza("ciao")


def test_cassaforte_cifrata(tmp_path):
    from sosia.cassaforte import Cassaforte
    s = sessione()
    e = s.pseudonimizza(TESTO)
    c = Cassaforte(tmp_path, metodo="parola", parola="una-parola-lunga-di-prova")
    f = c.salva(s, "prova")
    assert "Rossi" not in f.read_text(encoding="utf-8")
    assert c.carica("prova").ripristina(e.testo).testo == TESTO
    with pytest.raises(Exception):
        Cassaforte(tmp_path, metodo="parola", parola="parola-sbagliata-lunga").carica("prova")


# ------------------------------------------------------------------ formati
def test_docx_conserva_i_run(tmp_path):
    import io
    import zipfile
    from sosia.formati import Verso, elabora_bytes
    doc = ('<w:document xmlns:w="w"><w:body><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Il sig. Ma</w:t></w:r>'
           '<w:r><w:t xml:space="preserve">rio Rossi, nato il 01/02/1980.</w:t></w:r></w:p></w:body></w:document>')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", doc)
    s = sessione()
    nuovo, _ = elabora_bytes(b.getvalue(), ".docx", Verso(s))
    x = zipfile.ZipFile(io.BytesIO(nuovo)).read("word/document.xml").decode()
    assert "Rossi" not in x and "<w:b/>" in x and x.count("<w:t") == 2
    tornato, _ = elabora_bytes(nuovo, ".docx", Verso(s, "ripristina"))
    x2 = zipfile.ZipFile(io.BytesIO(tornato)).read("word/document.xml").decode()
    testo = lambda x: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", x))  # noqa: E731
    assert testo(x2) == testo(doc) and "<w:b/>" in x2  # il testo torna identico; un nome spezzato finisce in un solo run


def test_json_con_chiavi_nome_cognome():
    import json
    from sosia.formati import Verso, elabora_bytes
    s = sessione()
    dati = json.dumps({"nome": "Mario", "cognome": "Rossi", "note": "Il sig. Rossi ha chiamato."}).encode()
    nuovo, _ = elabora_bytes(dati, ".json", Verso(s))
    assert b"Rossi" not in nuovo and b"Mario" not in nuovo
    tornato, _ = elabora_bytes(nuovo, ".json", Verso(s, "ripristina"))
    assert json.loads(tornato) == json.loads(dati)


def test_pdf_nuovo_leggibile():
    from sosia.formati.pdf import estrai_testo, scrivi_pdf
    b = scrivi_pdf(["Riga uno con è e à\nRiga due"])
    assert "Riga due" in estrai_testo(b)[0]


def test_modalita_date_nascita_per_agenti():
    s = sessione(date="nascita")
    t = "Il sig. Mario Rossi, nato il 14/03/1978, ha l'appuntamento il 05/11/2026 alle 10."
    e = s.pseudonimizza(t)
    assert "05/11/2026" in e.testo and "14/03/1978" not in e.testo
    assert s.istruzioni_oggi() == ""
    # una data vera scritta dal modello non si tocca; quella di nascita finta torna vera
    nascita_finta = (dt.date(1978, 3, 14) + dt.timedelta(days=s.delta)).strftime("%d/%m/%Y")
    r = s.ripristina(f"Nato il {nascita_finta}; promemoria il 06/11/2026.").testo
    assert r == "Nato il 14/03/1978; promemoria il 06/11/2026."


def test_flusso_trattiene_poco_e_ripristina_sempre():
    import random as rnd
    s = sessione(date="nascita")
    t = ("La sig.ra Anna Rossi, nata il 02/11/1981, IBAN IT60 X054 2811 1010 0000 0123 456, tel. 347 123 4567, "
         "anna.rossi@example.com, vive in Via Garibaldi 12, 00185 Roma. Il sig. Mario Rossi e M. Rossi sono parenti.")
    finto = s.pseudonimizza(t).testo
    atteso = s.ripristina(finto).testo
    for seme in range(25):  # pezzi di lunghezza casuale: il risultato deve essere sempre identico
        g = rnd.Random(seme)
        f, out, i = s.flusso(), [], 0
        while i < len(finto):
            k = g.randint(1, 9)
            out.append(f.scrivi(finto[i:i + k]))
            i += k
        out.append(f.chiudi())
        assert "".join(out) == atteso
    # 0.5.0: si trattiene al massimo un margine (il dato finto più lungo + 20 caratteri, tagliato a uno spazio);
    # il resto esce subito e alla chiusura esce tutto
    f = s.flusso()
    testo = "Domani il tempo sarà variabile con qualche schiarita nel pomeriggio e venti deboli da nord-ovest. " * 3
    uscito = f.scrivi(testo)
    assert testo.startswith(uscito) and len(f.buf) <= f._margine() + 20
    assert uscito + f.chiudi() == testo


def test_prefiltro_e_memoria():
    import time
    from sosia import prefiltro
    s = sessione(date="nascita")
    e = s.pseudonimizza("Ciao Claude, che tempo fa domani?", "auto")
    assert e.testo == "Ciao Claude, che tempo fa domani?" and s.statistiche["puliti"] == 1
    lungo = "You are an interactive agent. The user will ask you. " * 1200
    t0 = time.perf_counter(); prefiltro.esamina(lungo); assert time.perf_counter() - t0 < 0.05
    s.pseudonimizza("Il sig. Mario Rossi ha chiamato.", "auto")
    prima = s.statistiche["regole"]
    s.pseudonimizza("Il sig. Mario Rossi ha chiamato.", "auto")
    assert s.statistiche["regole"] == prima and s.statistiche["memoria"] >= 1
    # un nome registrato dopo invalida solo i testi che lo contengono
    s.pseudonimizza("Ho visto Rossi ieri.", "auto")
    s.pseudonimizza("La dott.ssa Giulia Ferrandi è arrivata.", "auto")
    r = s.pseudonimizza("Ho visto Rossi ieri.", "auto")
    assert "Rossi" not in r.testo


def test_modello_in_caricamento_parole_sconosciute_sostituite():
    s = sessione(date="nascita")
    s.ner_atteso = True
    e = s.pseudonimizza("Sabato ceniamo da Xiomara a Squinzano.", "auto")
    assert "Xiomara" not in e.testo and "Squinzano" not in e.testo
    assert s.ripristina(e.testo).testo == "Sabato ceniamo da Xiomara a Squinzano."
