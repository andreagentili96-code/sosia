"""Cassaforte delle mappe: solo in locale, cifrate, con scadenza.

Formato del file (.sosia): JSON con intestazione in chiaro (versione, id, scadenza, metodo) e dati cifrati
con AES-256-GCM. L'intestazione è dato autenticato (AAD): non si può allungare la scadenza senza la chiave.

Chiave:
- «dpapi» (predefinito su Windows): chiave casuale di 32 byte protetta con DPAPI dell'utente Windows
  (CryptProtectData). Il file si apre solo con lo stesso utente sullo stesso PC.
- «parola»: chiave derivata con scrypt da una parola d'ordine (variabile SOSIA_PAROLA o argomento).
"""
from __future__ import annotations

import base64
import ctypes
import datetime as dt
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .sessione import Sessione, SessioneScaduta


def cartella_predefinita() -> Path:
    base = os.environ.get("SOSIA_CASSAFORTE")
    if base:
        return Path(base)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "sosia" / "sessioni"
    return Path.home() / ".local" / "share" / "sosia" / "sessioni"


# ------------------------------------------------------------------ DPAPI
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(b: bytes) -> _BLOB:
    buf = ctypes.create_string_buffer(b, len(b))
    blob = _BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob._tieni = buf  # il buffer deve vivere quanto la struttura
    return blob


def _dpapi(dati: bytes, proteggi: bool) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI esiste solo su Windows: usare il metodo «parola»")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    ingresso, uscita = _blob(dati), _BLOB()
    entropia = _blob(b"sosia-v1")
    fn = crypt32.CryptProtectData if proteggi else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(ingresso), None, ctypes.byref(entropia), None, None, 0x1, ctypes.byref(uscita))
    if not ok:
        raise OSError("DPAPI ha rifiutato l'operazione (utente o PC diversi?)")
    try:
        return ctypes.string_at(uscita.pbData, uscita.cbData)
    finally:
        kernel32.LocalFree(uscita.pbData)


def _scrypt(parola: str, sale: bytes) -> bytes:
    return hashlib.scrypt(parola.encode("utf-8"), salt=sale, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)


class Cassaforte:
    def __init__(self, cartella: str | Path | None = None, metodo: str | None = None, parola: str | None = None):
        self.cartella = Path(cartella) if cartella else cartella_predefinita()
        self.parola = parola if parola is not None else os.environ.get("SOSIA_PAROLA")
        self.metodo = metodo or ("parola" if self.parola else ("dpapi" if sys.platform == "win32" else "parola"))
        if self.metodo == "parola" and not self.parola:
            raise ValueError("Metodo «parola» senza parola d'ordine: impostare SOSIA_PAROLA")
        if self.metodo == "parola" and len(self.parola) < 12:
            raise ValueError("La parola d'ordine deve avere almeno 12 caratteri")

    def _file(self, nome: str) -> Path:
        sicuro = "".join(c for c in nome if c.isalnum() or c in "-_")[:64]
        if not sicuro:
            raise ValueError("nome di sessione non valido")
        return self.cartella / f"{sicuro}.sosia"

    def salva(self, sessione: Sessione, nome: str | None = None) -> Path:
        self.cartella.mkdir(parents=True, exist_ok=True)
        chiaro = json.dumps(sessione.a_dizionario(), ensure_ascii=False).encode("utf-8")
        testa = {"versione": 1, "id": sessione.id, "scadenza": sessione.scadenza, "metodo": self.metodo}
        if self.metodo == "dpapi":
            chiave = secrets.token_bytes(32)
            testa["chiave"] = base64.b64encode(_dpapi(chiave, True)).decode()
        else:
            sale = secrets.token_bytes(16)
            testa["sale"] = base64.b64encode(sale).decode()
            chiave = _scrypt(self.parola, sale)
        aad = json.dumps(testa, sort_keys=True).encode()
        nonce = secrets.token_bytes(12)
        cifrato = AESGCM(chiave).encrypt(nonce, chiaro, aad)
        f = self._file(nome or sessione.id)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"testa": testa, "nonce": base64.b64encode(nonce).decode(),
                                   "dati": base64.b64encode(cifrato).decode()}), encoding="utf-8")
        os.replace(tmp, f)
        return f

    def carica(self, nome: str, ner=None) -> Sessione:
        f = self._file(nome)
        j = json.loads(f.read_text(encoding="utf-8"))
        testa = j["testa"]
        if dt.datetime.now(dt.timezone.utc) > dt.datetime.fromisoformat(testa["scadenza"]):
            self.elimina(nome)
            raise SessioneScaduta(f"Sessione «{nome}» scaduta: file eliminato")
        if testa["metodo"] == "dpapi":
            chiave = _dpapi(base64.b64decode(testa["chiave"]), False)
        else:
            if not self.parola:
                raise ValueError("Serve la parola d'ordine (SOSIA_PAROLA)")
            chiave = _scrypt(self.parola, base64.b64decode(testa["sale"]))
        aad = json.dumps(testa, sort_keys=True).encode()
        chiaro = AESGCM(chiave).decrypt(base64.b64decode(j["nonce"]), base64.b64decode(j["dati"]), aad)
        return Sessione.da_dizionario(json.loads(chiaro.decode("utf-8")), ner)

    def esiste(self, nome: str) -> bool:
        return self._file(nome).exists()

    def elimina(self, nome: str) -> bool:
        f = self._file(nome)
        if not f.exists():
            return False
        try:  # sovrascrittura prima della cancellazione (utile su dischi tradizionali, non garantita su SSD)
            f.write_bytes(secrets.token_bytes(f.stat().st_size))
        finally:
            f.unlink()
        return True

    def elenco(self) -> list[dict]:
        out = []
        if not self.cartella.exists():
            return out
        for f in sorted(self.cartella.glob("*.sosia")):
            try:
                t = json.loads(f.read_text(encoding="utf-8"))["testa"]
                scaduta = dt.datetime.now(dt.timezone.utc) > dt.datetime.fromisoformat(t["scadenza"])
                out.append({"nome": f.stem, "scadenza": t["scadenza"], "metodo": t["metodo"], "scaduta": scaduta})
            except Exception:
                out.append({"nome": f.stem, "errore": "file illeggibile"})
        return out

    def pulisci(self) -> int:
        n = 0
        for v in self.elenco():
            if v.get("scaduta"):
                n += self.elimina(v["nome"])
        return n
