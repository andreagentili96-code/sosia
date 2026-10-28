"""0.5.0, date: «nel dubbio si sposta». Ogni data riconoscibile cambia, il ritorno resta identico. Dati inventati."""
from sosia import Sessione


def _giro(testo):
    s = Sessione()
    e = s.pseudonimizza(testo)
    assert s.ripristina(e.testo).testo == testo
    return e.testo


def test_date_ambigue_spostate():
    casi = [
        ("Statement period 02/01/2025 - 02/28/2025\n\n02/03  Direct deposit - PAYROLL  +$2,490.00\n", "02/03"),
        ("Notice date: May 2, 2025\nYour account is past due.\n  April charges ...... $201.77\n", "April"),
        ("We were billed each June for the policy. Signed on 3/14/2025.", "June"),
        ("Ci siamo visti il 3/10 in studio, come concordato.", "3/10"),
        ("Il contratto è stato firmato nel 2019 a Brescia.", "2019"),
    ]
    for testo, vero in casi:
        assert vero not in _giro(testo), testo


def test_quantita_non_spostate():
    for testo in ("Aggiungere 3/4 di litro d'acqua.", "Servizio attivo 24/7.", "Fatturato di 2019 euro nel mese.",
                  "Siamo in 2030 dipendenti."):
        assert _giro(testo) == testo


def test_codice_con_anno_sostituito():
    testo = "Spett. Comune, data 3 marzo 2025.\n[x] pratica edilizia n. PE 2022/0457 relativa all'ampliamento;\n"
    finto = _giro(testo)
    assert "2022/0457" not in finto and "3 marzo 2025" not in finto


def test_relative_senza_data_restano():
    testo = "Ci vediamo venerdì prossimo per firmare."
    assert _giro(testo) == testo
