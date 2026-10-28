"""Un test per ogni causa di ritorno non identico o di cronologia rotta trovata nei banchi (0.3.0 → 0.4.0). Dati inventati."""
import datetime as dt

import pytest

from sosia import Configurazione, Sessione
from sosia.date import trova_date


def andata_ritorno(testo, **cfg):
    for seme in (1, 2, 3, 4, 5):
        s = Sessione(Configurazione(seme=seme, **cfg))
        e = s.pseudonimizza(testo, usa_ner=False)
        assert s.ripristina(e.testo).testo == testo
        assert "SEGNAPOSTO" not in e.conteggi, "la causa va corretta, non coperta dal segnaposto"
    return s, e


@pytest.mark.parametrize("testo", [
    # numero di pratica «07/2025» che sostituiva gli stessi caratteri dentro le date «01/07/2025»
    "ESTRATTO CONTO N. 07/2025\nPeriodo: dal 01/07/2025 al 31/07/2025\n02/07/2025  Bonifico a Rossetti Paolo  180,00",
    # sigla dello stato senza virgola
    "Taxpayer: Maria Delgado\n4410 Alameda Avenue\nEl Paso TX 79936-5120",
    # numero di conto con lettere
    "Statement date: 08/19/2025          Account number: PA-7730418\nPlease include your account number PA-7730418.",
    # «Perugia al Fg.»: la città non si mangia la parola catastale
    "Immobile sito nel Comune di Perugia al Fg. 211 Part. 1042 Sub. 18 (appartamento, cat. A/2).",
    # «the 6th day of March, 2025»
    "DATED this 6th day of March, 2025.\nSigned by John Carter.",
    # civico inglese preso come numero di pratica («on file: 19»)
    "Patient address on file: 19 Glenmore Road, Worcester, MA 01604",
    # cognome con maiuscole miste scritto in due modi
    "Name: Mr Iain MACLEOD-Wood\nDeclaration signed by Iain MacLeod-Wood on 20 May 2025.",
    # civico ripetuto su due righe
    "PROPRIETOR: (1) KHAN, Imran Ahmed of 27 Ravensworth\nTerrace, Harrogate HG1 5LQ and (2) Saira Khan of 29 Ravensworth Terrace.",
])
def test_ritorno_identico(testo):
    andata_ritorno(testo)
    andata_ritorno(testo, date="nascita")


def _spostate(testo, convenzione="DMY"):
    s = Sessione(Configurazione(seme=9))
    e = s.pseudonimizza(testo, usa_ner=False)
    assert s.ripristina(e.testo).testo == testo
    vere = trova_date(testo, 2025, True, convenzione)
    finte = trova_date(e.testo, 2025 + s.delta // 365, True, convenzione)
    return s, vere, finte


@pytest.mark.parametrize("testo,attese", [
    ("Milano, 2 novembre 2025\nCome da sollecito del 3 u.s. e del 9 corr., la invitiamo a pagare entro il 5 p.v.",
     ["2025-11-02", "2025-10-03", "2025-11-09", "2025-12-05"]),
    ("Roma, 10 aprile 2025. Ci vediamo giovedì 8 e venerdì 9.", ["2025-04-10", "2025-05-08", "2025-05-09"]),
    ("Periodo dal 3 al 10 marzo 2025; competenza 07/2025; Q3 2025; terzo trimestre del 2024.",
     ["2025-03-03", "2025-03-10", "2025-07-15", "2025-08-15", "2024-08-15"]),
    ("Atto del ventidue del mese di luglio duemilaventicinque.", ["2025-07-22"]),
])
def test_date_parziali_e_relative(testo, attese):
    s, vere, finte = _spostate(testo)
    assert [str(d.data) for d in vere] == attese
    assert len(finte) == len(vere)
    for v, f in zip(vere, finte):
        if v.granularita == "trimestre":
            atteso = v.data + dt.timedelta(days=s.delta)
            assert (f.data.year, (f.data.month - 1) // 3) == (atteso.year, (atteso.month - 1) // 3)
        elif v.granularita == "mese":
            atteso = v.data + dt.timedelta(days=s.delta)
            assert (f.data.year, f.data.month) == (atteso.year, atteso.month)
        else:
            assert f.data == v.data + dt.timedelta(days=s.delta), (v.testo, f.testo)


def test_intervallo_inglese_e_anni():
    s, vere, finte = _spostate("Stay March 3-10, 2025; contract 2019-2021; since 2018.", "MDY")
    assert [str(d.data) for d in vere][:2] == ["2025-03-03", "2025-03-10"]
    assert [d.data.year for d in vere][2:] == [2019, 2021, 2018]


def test_on_the_14th():
    s, vere, finte = _spostate("Dated 2 July 2025. The auditor arrives on the 14th.", "DMY")
    assert str(vere[-1].data) == "2025-07-14"
    assert finte[-1].data == vere[-1].data + dt.timedelta(days=s.delta)


def test_segnaposto_quando_il_finto_non_tornerebbe():
    s = Sessione(Configurazione(seme=1))
    s.pseudonimizza("Mario Rossi abita a Bologna.", usa_ner=False)
    alias = s.unita["rossi"]["f"]
    testo = f"Il fornitore {alias.lower()}-servizi.it e la ditta «{alias}» hanno firmato il 3 marzo 1980."
    e = s.pseudonimizza(testo, usa_ner=False)
    assert s.ripristina(e.testo).testo == testo


def test_flusso_civico_e_telefono():
    s = Sessione(Configurazione(seme=4))
    t = "Patient: HERNANDEZ, Ana, phone (305) 555-0187, address 940 Coral Reef Drive, Miami, FL 33145."
    e = s.pseudonimizza(t, usa_ner=False)
    f = s.flusso()
    out = "".join(f.scrivi(e.testo[i:i + 7]) for i in range(0, len(e.testo), 7)) + f.chiudi()
    assert out == t


def test_testo_lungo_a_blocchi():
    """Prompt lungo: i blocchi senza nulla di personale restano com'erano, gli altri si proteggono e tornano identici."""
    pulito = "You are an interactive agent that helps users with software engineering tasks. " * 120
    testo = ("Milano, 2 novembre 2025\n\n" + pulito + "\n\nIl sig. Mario Rossi (tel. 347 123 4567) ha pagato il 3 u.s.\n\n"
             + pulito + "\n\nRossi abita in via dei Mille 22, 20121 Milano.")
    s = Sessione(Configurazione(seme=3))
    e = s.pseudonimizza(testo, usa_ner=False)
    assert len(testo) > 6000
    for v in ("Rossi", "347 123 4567", "dei Mille", "2 novembre 2025"):
        assert v not in e.testo, v
    assert pulito in e.testo
    assert s.ripristina(e.testo).testo == testo
