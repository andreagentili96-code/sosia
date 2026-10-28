"""0.6.0: elenchi ufficiali (ISTAT, OS Open Names, ONS, Census, Wikidata) usati solo con un contesto. Dati inventati."""
import hashlib
import json
from pathlib import Path

from sosia import Sessione

DIZ = Path(__file__).resolve().parent.parent / "sosia" / "dizionari"


def test_estratti_integri():
    fonti = json.loads((DIZ / "FONTI.json").read_text(encoding="utf-8"))
    for nome, h in fonti["prodotti"].items():
        assert hashlib.sha256((DIZ / nome).read_bytes()).hexdigest() == h, nome


def _giro(testo):
    s = Sessione()
    e = s.pseudonimizza(testo, usa_ner=False)
    assert s.ripristina(e.testo).testo == testo
    return e.testo


def test_luoghi_con_contesto():
    casi = [
        ("STAZIONE CARABINIERI DI CEPPALONI\nVerbale di denuncia.", ["CEPPALONI"]),
        ("Il notaio in Vallo della Lucania ha ricevuto l'atto.", ["Vallo della Lucania"]),
        ("Our client lives at Rose Cottage, Achmore, Isle of Lewis HS2 9DN.", ["Rose", "HS2 9DN"]),
        ("Flat 3/1, 8 Trongate, Glasgow G1 5EZ", ["Trongate"]),
        ("Mailing address: RR 2 Box 14, Many Farms, AZ 86503.", ["RR 2 Box 14"]),
    ]
    for testo, veri in casi:
        finto = _giro(testo)
        for v in veri:
            assert v not in finto, (v, finto)


def test_parole_comuni_non_diventano_luoghi():
    for testo in ("Il ponte è chiuso e il re ha parlato.", "Abbiamo visto il Ponte di ferro e la Villa comunale.",
                  "The Mill was closed and the Bank of England raised rates."):
        assert _giro(testo) == testo
