"""Alias secondo la lingua e l'origine del nome; numeri di legge citati con la data. Dati inventati."""
from __future__ import annotations

from sosia import Configurazione, Sessione, dati
from sosia import dati_en as DE
from sosia.dati import norm


def _alias(testo, *chiavi):
    s = Sessione(Configurazione(seme=7))
    e = s.pseudonimizza(testo, usa_ner=False)
    assert s.ripristina(e.testo).testo == testo
    return s, [s.unita[norm(k)]["f"] for k in chiavi]


def test_nomi_inglesi_in_testo_inglese_alias_inglesi():
    _, (m, b, k, mi) = _alias("Thank you for your visit with Dr. Michael Brown. Sincerely, Karen Miller, Billing Office.",
                              "michael", "brown", "karen", "miller")
    assert m in DE.ALIAS_FIRST_M and k in DE.ALIAS_FIRST_F
    assert b in DE.ALIAS_SURNAMES and mi in DE.ALIAS_SURNAMES


def test_nome_italiano_in_testo_inglese_resta_italiano():
    _, (a, r) = _alias("Dear Ms. Rossi, our client Anna Rossi of Milan wrote to us on March 4, 2025 about the lease.",
                       "anna", "rossi")
    assert r in dati.ALIAS_COGNOMI and a in dati.ALIAS_NOMI_F


def test_testo_italiano_alias_italiani():
    _, (j, s) = _alias("Il sig. John Smith, nato a Londra, ha firmato il contratto con la sig.ra Anna Rossi.", "john", "smith")
    assert j in dati.ALIAS_NOMI_M and s in dati.ALIAS_COGNOMI


def test_testo_misto_segue_la_frase():
    _, (sa, w) = _alias("Ciao Sarah, ti mando il contratto firmato dal notaio. Dear Mr Walsh, please find the lease attached.",
                        "sarah", "walsh")
    assert sa in dati.ALIAS_NOMI_F and w in DE.ALIAS_SURNAMES


def test_numero_di_legge_con_data_non_sostituito():
    for t in ("Agirò ai sensi della legge 10 dicembre 2014 n. 162 e dell'art. 316-bis c.c. entro il 25/10/2026.",
              "Visto il D.Lgs. 30 giugno 2003, n. 196, il sig. Mario Rossi chiede l'accesso il 12/10/2026.",
              "Ai sensi del D.P.R. 22/12/1986 n. 917 la fattura del 03/03/2026 è deducibile."):
        s = Sessione(Configurazione(seme=7))
        e = s.pseudonimizza(t, usa_ner=False)
        for numero in ("n. 162", "n. 196", "n. 917"):
            if numero in t:
                assert numero in e.testo, (numero, e.testo)
        assert s.ripristina(e.testo).testo == t


def test_numero_di_pratica_dopo_una_data_resta_sostituito():
    t = "Con lettera del 10 dicembre 2025 n. 4812 la banca ha risposto al sig. Mario Rossi."
    s = Sessione(Configurazione(seme=7))
    assert "4812" not in s.pseudonimizza(t, usa_ner=False).testo
