"""0.5.0, nomi e luoghi: soprannomi in mezzo, coppie, iniziali, minuscolo, vie senza «via», carte. Dati inventati."""
import re

from sosia import Sessione


def _giro(testo):
    s = Sessione()
    e = s.pseudonimizza(testo, usa_ner=False)
    assert s.ripristina(e.testo).testo == testo
    return e.testo


def test_nomi_difficili():
    casi = [
        ("Investigator Robert \"Bobby\" McAllister was assigned to the file.", ["McAllister", "Robert"]),
        ("Parents of the bride: Kenji and Ruth Nakagawa, (843) 555-0161", ["Kenji", "Nakagawa"]),
        ("- G. Rosa, consigliere\n- M. Guerra, consigliere\n", ["Rosa", "Guerra"]),
        ("Funge da segretario il dott. G. Righetti.", ["Righetti"]),
        ("Mrs. Nguyen is known to the nursing staff as \"Lani\".", ["Lani"]),
        ("[12/10/25, 09:13] giulia: ciao marco, porto io la torta\n[12/10/25, 09:14] Pia: saluta la zia carmela!", ["marco", "carmela", "giulia"]),
    ]
    for testo, veri in casi:
        finto = _giro(testo)
        for v in veri:  # parola intera: un alias come «giuliana» non è una fuga di «giulia»
            assert not re.search(rf"(?<!\w){re.escape(v)}(?!\w)", finto), (v, finto)


def test_vie_senza_prefisso_e_carte():
    casi = [
        ("Indirizzo: Parma, Bixio 18, interno 4, 43125", ["Bixio", "43125"]),
        ("residente in Bari, 70125, Re David 220 (quartiere Carrassi)", ["Re David"]),
        ("Domicilio fiscale: Madonna Pellegrina 40, 35137 Padova", ["Madonna Pellegrina"]),
        ("dell'Industria 7, Jesi.", ["dell'Industria"]),
        ("Down payment charged to Visa 4450_8186_8485_0912, expiration on file.", ["4450_8186_8485_0912"]),
        ("Marco: spedisci tutto a casa nostra, 14 Egerton Road, Manchester M14 6RH\nNonna: va bene", ["Egerton", "M14 6RH"]),
    ]
    for testo, veri in casi:
        finto = _giro(testo)
        for v in veri:
            assert v not in finto, (v, finto)
