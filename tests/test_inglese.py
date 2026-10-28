"""English (US/UK): validators, date conventions, surrogates and round trip. Invented data only."""
import random

from sosia import Configurazione, Sessione
from sosia import inglese as EN
from sosia.date import convenzione_date, sposta, trova_date


def test_validatori_e_finti():
    rng = random.Random(3)
    for _ in range(50):
        assert EN.ssn_valido(EN.finto_ssn(rng))
        assert EN.nhs_valido(EN.finto_nhs(rng))
        assert EN.aba_valido(EN.finto_aba(rng))
        assert EN.nino_valido(EN.finto_nino(rng))
        assert EN.itin_valido(EN.finto_itin(rng))
    assert EN.nhs_valido("943 476 5919")
    assert not EN.ssn_valido("666-12-3456")


def test_lingua_e_convenzione():
    us = "Dear Mr. Smith, your appointment on 03/11/2025 is confirmed. Call (305) 555-0101. Thanks, the clinic."
    uk = "Dear Mrs Jones, your appointment on 03/11/2025 at the NHS clinic, London SW1A 1AA, is confirmed."
    assert EN.lingua(us) == "en" and EN.lingua("Il sottoscritto Mario Rossi, nato a Roma il 3 marzo 1970") == "it"
    assert convenzione_date(us, "en") == "MDY" and convenzione_date(uk, "en") == "DMY"
    assert convenzione_date("Signed 13/04/2025", "en") == "DMY"
    d = trova_date("on 03/11/2025", convenzione="MDY")[0]
    assert (d.data.month, d.data.day) == (3, 11)
    t = "Seen on March 4th, 2025 and Jan. 15."
    ds = trova_date(t, 2025, True, "MDY")
    assert [sposta(x, t, -14, True) for x in ds] == ["February 18th, 2025", "Jan. 1"]


def test_andata_e_ritorno_inglese():
    t = ("Patient: O'CONNOR, Declan\nSSN 219-09-9999, NHS number 943 476 5919, phone (305) 555-0187.\n"
         "Address: 940 Coral Reef Drive, Apt 4D, Miami, FL 33145. Seen on 06/30/2025 by Dr. Priya Raman.\n"
         "Routing number (ABA): 021000021, account number 4402331897. Plate ABC D12.")
    s = Sessione(Configurazione(seme=5))
    e = s.pseudonimizza(t, usa_ner=False)
    for v in ("O'CONNOR", "Declan", "219-09-9999", "943 476 5919", "555-0187", "Coral Reef", "Miami", "33145",
              "Raman", "021000021", "4402331897", "ABC D12", "06/30/2025"):
        assert v not in e.testo, v
    assert s.ripristina(e.testo).testo == t
    # il modello riscrive: cognome da solo, possessivo, data in lettere
    cognome_finto = s.unita["raman"]["f"]
    risposta = f"Dr. {cognome_finto}'s note is clear."
    assert s.ripristina(risposta).testo == "Dr. Raman's note is clear."
