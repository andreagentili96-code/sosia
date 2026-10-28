"""Proxy HTTP locale compatibile con le API di Anthropic (/v1/messages) e OpenAI (/v1/chat/completions,
/v1/responses). In andata pseudonimizza, al ritorno ripristina, anche in streaming.

Uso: sosia proxy --porta 8787, poi nel client ANTHROPIC_BASE_URL=http://127.0.0.1:8787 oppure
OPENAI_BASE_URL=http://127.0.0.1:8787/v1. Le chiavi API del client passano intatte verso il fornitore:
lo scudo non le legge, non le salva e non le registra.

Sicurezza locale: ascolta solo su 127.0.0.1; rifiuta le richieste dei browser da altri siti (intestazione
Origin) e gli Host diversi da localhost (difesa dal DNS rebinding). Gli endpoint /sosia/* (servizio per le
applicazioni integrate) richiedono il gettone locale SOSIA_TOKEN, perché ripristinare equivale a decifrare.
"""
from __future__ import annotations

import asyncio
import copy
import hmac
import json
import logging
import os
import secrets
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .sessione import Configurazione, Sessione

log = logging.getLogger("sosia.proxy")

ESCLUSE_RICHIESTA = {"host", "content-length", "accept-encoding", "connection", "transfer-encoding"}
ESCLUSE_RISPOSTA = {"content-length", "content-encoding", "transfer-encoding", "connection"}


class ErroreScudo(Exception):
    def __init__(self, messaggio: str, stato: int = 400):
        super().__init__(messaggio)
        self.stato = stato


class Scudo:
    """Sessioni del proxy, una per nome (intestazione X-Sosia-Sessione), salvate cifrate se c'è una cassaforte."""

    def __init__(self, cassaforte=None, config: Configurazione | None = None, ner=None):
        self.cassaforte = cassaforte
        self.config = config or Configurazione()
        self.ner = ner
        self.stato_ner = "pronto" if ner is not None else "nessuno"
        self._sessioni: dict[str, Sessione] = {}
        self._lock = asyncio.Lock()

    def imposta_ner(self, ner, stato: str = "pronto"):
        """Il modello si carica in sottofondo: finché non è pronto le sessioni lavorano con le sole regole."""
        self.ner = ner
        self.stato_ner = stato
        for s in self._sessioni.values():
            s.ner = ner
            s.ner_atteso = False

    def sessione(self, nome: str) -> Sessione:
        s = self._sessioni.get(nome)
        if s is not None and s.scaduta():
            s = None
            self._sessioni.pop(nome, None)
        if s is None:
            if self.cassaforte is not None and self.cassaforte.esiste(nome):
                try:
                    s = self.cassaforte.carica(nome, self.ner)
                except Exception as e:
                    log.warning("sessione %s non caricata (%s): ne creo una nuova", nome, type(e).__name__)
            if s is None:
                s = Sessione(self.config, ner=self.ner)
            s.ner_atteso = self.ner is None and self.stato_ner == "caricamento"
            s.config.ner_modo = self.config.ner_modo  # una sessione salvata con la 0.1.0 prende la modalità attuale
            self._sessioni[nome] = s
        return s

    async def salva(self, nome: str):
        if self.cassaforte is not None:
            async with self._lock:
                self.cassaforte.salva(self._sessioni[nome], nome)


# ------------------------------------------------------------------ visita delle richieste
def _ricorsivo(v, f):
    if isinstance(v, str):
        return f(v)
    if isinstance(v, list):
        return [_ricorsivo(x, f) for x in v]
    if isinstance(v, dict):
        return {k: _ricorsivo(x, f) for k, x in v.items()}
    return v


def _json_stringa(s: str, f) -> str:
    try:
        return json.dumps(_ricorsivo(json.loads(s), f), ensure_ascii=False)
    except (ValueError, TypeError):
        return f(s)


class Visitatore:
    def __init__(self, s: Sessione, immagini: str, ner_sistema: bool = False):
        self.s = s
        self.immagini = immagini
        self.ner_sistema = ner_sistema
        self.sistema = False  # vero mentre si visita il prompt di sistema: lì solo regole (il modello NER è lento)
        self.avvisi: list[str] = []

    def _immagine(self):
        if self.immagini == "blocca":
            raise ErroreScudo("La richiesta contiene immagini: lo scudo non può proteggerle (serve l'OCR). "
                              "Toglile o avvia il proxy con --immagini lascia.", 422)
        self.avvisi.append("immagine inoltrata senza protezione")

    # Anthropic -------------------------------------------------------
    def anthropic(self, corpo: dict, f, copia: bool = True) -> dict:
        c = copy.deepcopy(corpo) if copia else corpo
        self.sistema = not self.ner_sistema
        if isinstance(c.get("system"), str):
            c["system"] = f(c["system"])
        elif isinstance(c.get("system"), list):
            c["system"] = [self._blocco_a(b, f) for b in c["system"]]
        self.sistema = False
        for m in c.get("messages", []):
            if isinstance(m.get("content"), str):
                m["content"] = f(m["content"])
            elif isinstance(m.get("content"), list):
                m["content"] = [self._blocco_a(b, f) for b in m["content"]]
        return c

    def _blocco_a(self, b, f):
        if not isinstance(b, dict):
            return b
        t = b.get("type")
        if t == "text":
            b["text"] = f(b.get("text", ""))
        elif t == "tool_use":
            b["input"] = _ricorsivo(b.get("input", {}), f)
        elif t == "tool_result":
            if isinstance(b.get("content"), str):
                b["content"] = f(b["content"])
            elif isinstance(b.get("content"), list):
                b["content"] = [self._blocco_a(x, f) for x in b["content"]]
        elif t == "document":
            src = b.get("source", {})
            if src.get("type") == "text":
                src["data"] = f(src.get("data", ""))
            elif src.get("type") == "base64" and src.get("media_type") == "application/pdf":
                import base64
                from .formati.pdf import estrai_testo
                testo = "\n\f\n".join(estrai_testo(base64.b64decode(src["data"])))
                if not testo.strip():
                    raise ErroreScudo("PDF senza testo estraibile (scansione): serve l'OCR", 422)
                b["source"] = {"type": "text", "media_type": "text/plain", "data": f(testo)}
                self.avvisi.append("PDF convertito in testo prima dell'invio")
            elif src.get("type") == "content":
                src["content"] = [self._blocco_a(x, f) for x in src.get("content", [])]
            else:
                raise ErroreScudo("Documento in un formato non protetto (URL o file remoto)", 422)
            for k in ("title", "context"):
                if isinstance(b.get(k), str):
                    b[k] = f(b[k])
        elif t == "image":
            self._immagine()
        elif t in ("thinking", "redacted_thinking"):
            pass  # firmati dal fornitore: non si toccano (contengono già i dati finti dei turni precedenti)
        elif t == "search_result":
            b["content"] = [self._blocco_a(x, f) for x in b.get("content", [])]
            for k in ("title", "source"):
                if isinstance(b.get(k), str):
                    b[k] = f(b[k])
        return b

    # OpenAI chat -----------------------------------------------------
    def openai_chat(self, corpo: dict, f, copia: bool = True) -> dict:
        c = copy.deepcopy(corpo) if copia else corpo
        for m in c.get("messages", []):
            if isinstance(m.get("content"), str):
                m["content"] = f(m["content"])
            elif isinstance(m.get("content"), list):
                for p in m["content"]:
                    if p.get("type") == "text":
                        p["text"] = f(p.get("text", ""))
                    elif p.get("type") in ("image_url", "input_audio", "file"):
                        self._immagine()
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                if isinstance(fn.get("arguments"), str):
                    fn["arguments"] = _json_stringa(fn["arguments"], f)
            if isinstance(m.get("name"), str) and m.get("role") == "user":
                m["name"] = f(m["name"])
        return c

    # OpenAI responses ------------------------------------------------
    def openai_responses(self, corpo: dict, f, copia: bool = True) -> dict:
        c = copy.deepcopy(corpo) if copia else corpo
        if isinstance(c.get("instructions"), str):
            c["instructions"] = f(c["instructions"])
        if isinstance(c.get("input"), str):
            c["input"] = f(c["input"])
        elif isinstance(c.get("input"), list):
            for it in c["input"]:
                self._voce_r(it, f)
        return c

    def _voce_r(self, it, f):
        if not isinstance(it, dict):
            return
        if isinstance(it.get("content"), str):
            it["content"] = f(it["content"])
        elif isinstance(it.get("content"), list):
            for p in it["content"]:
                if p.get("type") in ("input_text", "output_text", "text"):
                    p["text"] = f(p.get("text", ""))
                elif p.get("type") in ("input_image", "input_file", "input_audio"):
                    self._immagine()
        if it.get("type") == "function_call" and isinstance(it.get("arguments"), str):
            it["arguments"] = _json_stringa(it["arguments"], f)
        if it.get("type") == "function_call_output" and isinstance(it.get("output"), str):
            it["output"] = f(it["output"])


def pseudonimizza_corpo(s: Sessione, corpo: dict, api: str, immagini: str = "blocca", ner_sistema: bool = False,
                        ner_budget: int = 20000) -> tuple[dict, list]:
    """Due passate: la prima registra tutte le persone della conversazione (senza copiare nulla), la seconda
    sostituisce. Così un «Rossi» nel primo messaggio è coperto anche se «Mario Rossi» compare solo nell'ultimo.
    Ogni testo già visto torna dalla memoria della sessione: costa solo il testo nuovo del turno.
    Modello NER in modalità «auto»: solo sulle frasi con parole maiuscole sconosciute; mai sul prompt di sistema
    né sul contesto iniettato dalla CLI (<system-reminder>); al massimo ner_budget caratteri per testo."""
    v = Visitatore(s, immagini, ner_sistema)
    metodo = {"anthropic": v.anthropic, "chat": v.openai_chat, "responses": v.openai_responses}[api]

    def modo(t: str):
        return False if (v.sistema or "<system-reminder>" in t[:200]) else "auto"
    metodo(corpo, lambda t: (s.pseudonimizza(t, modo(t), ner_budget), t)[1] if t else t, copia=False)
    avvisi: list[str] = []

    def f(t):
        if not t:
            return t
        e = s.pseudonimizza(t, modo(t), ner_budget)
        avvisi.extend(a for a in e.avvisi if a not in avvisi)
        return e.testo
    nuovo = metodo(corpo, f)
    return nuovo, avvisi + v.avvisi


def _aggiungi_nota_anthropic(corpo: dict, nota: str):
    if isinstance(corpo.get("system"), list):
        corpo["system"] = [{"type": "text", "text": nota}] + corpo["system"]
    elif corpo.get("system"):
        corpo["system"] = nota + "\n\n" + corpo["system"]
    else:
        corpo["system"] = nota


def _aggiungi_nota_openai(corpo: dict, nota: str, api: str):
    if api == "chat":
        corpo.setdefault("messages", []).insert(0, {"role": "system", "content": nota})
    else:
        corpo["instructions"] = nota + ("\n\n" + corpo["instructions"] if corpo.get("instructions") else "")


# ------------------------------------------------------------------ ripristino delle risposte
def ripristina_anthropic(s: Sessione, r: dict) -> dict:
    f = lambda t: s.ripristina(t).testo  # noqa: E731
    for b in r.get("content", []) or []:
        if b.get("type") == "text":
            b["text"] = f(b["text"])
        elif b.get("type") in ("tool_use", "server_tool_use"):
            b["input"] = _ricorsivo(b.get("input", {}), f)
    if isinstance(r.get("error"), dict) and isinstance(r["error"].get("message"), str):
        r["error"]["message"] = f(r["error"]["message"])
    return r


def ripristina_chat(s: Sessione, r: dict) -> dict:
    f = lambda t: s.ripristina(t).testo  # noqa: E731
    for ch in r.get("choices", []) or []:
        m = ch.get("message", {})
        if isinstance(m.get("content"), str):
            m["content"] = f(m["content"])
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function", {})
            if isinstance(fn.get("arguments"), str):
                fn["arguments"] = _json_stringa(fn["arguments"], f)
    return r


def ripristina_responses(s: Sessione, r: dict) -> dict:
    f = lambda t: s.ripristina(t).testo  # noqa: E731
    for it in r.get("output", []) or []:
        for p in it.get("content", []) or []:
            if isinstance(p.get("text"), str):
                p["text"] = f(p["text"])
        if isinstance(it.get("arguments"), str):
            it["arguments"] = _json_stringa(it["arguments"], f)
    if isinstance(r.get("output_text"), str):
        r["output_text"] = f(r["output_text"])
    return r


def _sse(evento: str | None, dati: dict | str) -> bytes:
    corpo = dati if isinstance(dati, str) else json.dumps(dati, ensure_ascii=False)
    return ((f"event: {evento}\n" if evento else "") + f"data: {corpo}\n\n").encode("utf-8")


async def _eventi(righe):
    """Raggruppa le righe SSE in eventi (nome, dati)."""
    nome, dati = None, []
    async for riga in righe:
        if riga == "":
            if dati or nome:
                yield nome, "\n".join(dati)
            nome, dati = None, []
        elif riga.startswith("event:"):
            nome = riga[6:].strip()
        elif riga.startswith("data:"):
            dati.append(riga[5:].lstrip())
    if dati or nome:
        yield nome, "\n".join(dati)


async def flusso_anthropic(s: Sessione, righe):
    blocchi: dict[int, dict] = {}
    async for nome, dati in _eventi(righe):
        try:
            d = json.loads(dati)
        except ValueError:
            yield _sse(nome, dati)
            continue
        t = d.get("type")
        if t == "content_block_start":
            cb = d.get("content_block", {})
            blocchi[d["index"]] = {"tipo": cb.get("type"), "flusso": s.flusso(), "json": ""}
            yield _sse(nome, d)
        elif t == "content_block_delta":
            b = blocchi.get(d["index"])
            delta = d.get("delta", {})
            if b and delta.get("type") == "text_delta":
                out = b["flusso"].scrivi(delta.get("text", ""))
                if out:
                    delta["text"] = out
                    yield _sse(nome, d)
            elif b and delta.get("type") == "input_json_delta":
                b["json"] += delta.get("partial_json", "")
            else:
                yield _sse(nome, d)
        elif t == "content_block_stop":
            b = blocchi.pop(d["index"], None)
            if b and b["tipo"] == "text":
                resto = b["flusso"].chiudi()
                if resto:
                    yield _sse("content_block_delta", {"type": "content_block_delta", "index": d["index"],
                                                       "delta": {"type": "text_delta", "text": resto}})
            elif b and b["tipo"] in ("tool_use", "server_tool_use"):
                testo = _json_stringa(b["json"], lambda x: s.ripristina(x).testo) if b["json"].strip() else ""
                if testo:
                    yield _sse("content_block_delta", {"type": "content_block_delta", "index": d["index"],
                                                       "delta": {"type": "input_json_delta", "partial_json": testo}})
            yield _sse(nome, d)
        elif t == "error" and isinstance(d.get("error"), dict):
            d["error"]["message"] = s.ripristina(str(d["error"].get("message", ""))).testo
            yield _sse(nome, d)
        else:
            yield _sse(nome, d)


async def flusso_chat(s: Sessione, righe):
    testo: dict[int, object] = {}
    strumenti: dict[int, dict] = {}
    ultimo = None

    def coda(meta, indice):
        out = []
        f = testo.pop(indice, None)
        resto = f.chiudi() if f else ""
        delta = {}
        if resto:
            delta["content"] = resto
        tc = strumenti.pop(indice, {})
        if tc:
            delta["tool_calls"] = []
            for i, x in sorted(tc.items()):
                x["function"]["arguments"] = _json_stringa(x["function"]["arguments"], lambda t: s.ripristina(t).testo) if x["function"]["arguments"] else ""
                delta["tool_calls"].append({"index": i, **x})
        if delta:
            out.append(_sse(None, {**meta, "choices": [{"index": indice, "delta": delta, "finish_reason": None}]}))
        return out

    async for _, dati in _eventi(righe):
        if dati.strip() == "[DONE]":
            if ultimo:
                for i in list(set(testo) | set(strumenti)):
                    for b in coda(ultimo, i):
                        yield b
            yield _sse(None, "[DONE]")
            continue
        try:
            d = json.loads(dati)
        except ValueError:
            yield _sse(None, dati)
            continue
        meta = {k: v for k, v in d.items() if k != "choices"}
        ultimo = meta
        nuove = []
        for ch in d.get("choices", []) or []:
            i = ch.get("index", 0)
            delta = ch.get("delta", {}) or {}
            if isinstance(delta.get("content"), str):
                f = testo.setdefault(i, s.flusso())
                delta["content"] = f.scrivi(delta["content"])
                if not delta["content"]:
                    del delta["content"]
            for tc in delta.pop("tool_calls", None) or []:
                x = strumenti.setdefault(i, {}).setdefault(tc.get("index", 0), {"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
                x["id"] = tc.get("id") or x["id"]
                fn = tc.get("function", {}) or {}
                x["function"]["name"] += fn.get("name") or ""
                x["function"]["arguments"] += fn.get("arguments") or ""
            if ch.get("finish_reason"):
                for b in coda(meta, i):
                    yield b
            if delta or ch.get("finish_reason") or ch.get("logprobs"):
                ch["delta"] = delta
                nuove.append(ch)
        if nuove or not d.get("choices"):
            d["choices"] = nuove
            yield _sse(None, d)


async def flusso_responses(s: Sessione, righe):
    testi: dict[tuple, object] = {}
    argomenti: dict[str, str] = {}
    f = lambda t: s.ripristina(t).testo  # noqa: E731
    async for nome, dati in _eventi(righe):
        try:
            d = json.loads(dati)
        except ValueError:
            yield _sse(nome, dati)
            continue
        t = d.get("type", nome)
        chiave = (d.get("item_id"), d.get("content_index"))
        if t == "response.output_text.delta":
            fl = testi.setdefault(chiave, s.flusso())
            out = fl.scrivi(d.get("delta", ""))
            if out:
                d["delta"] = out
                yield _sse(nome, d)
        elif t == "response.output_text.done":
            fl = testi.pop(chiave, None)
            resto = fl.chiudi() if fl else ""
            if resto:
                yield _sse("response.output_text.delta", {**{k: v for k, v in d.items() if k != "text"},
                                                          "type": "response.output_text.delta", "delta": resto})
            d["text"] = f(d.get("text", ""))
            yield _sse(nome, d)
        elif t == "response.function_call_arguments.delta":
            argomenti[d.get("item_id")] = argomenti.get(d.get("item_id"), "") + d.get("delta", "")
        elif t == "response.function_call_arguments.done":
            argomenti.pop(d.get("item_id"), None)
            d["arguments"] = _json_stringa(d.get("arguments", ""), f)
            yield _sse("response.function_call_arguments.delta", {**{k: v for k, v in d.items() if k != "arguments"},
                                                                  "type": "response.function_call_arguments.delta",
                                                                  "delta": d["arguments"]})
            yield _sse(nome, d)
        elif t in ("response.completed", "response.done", "response.incomplete"):
            if isinstance(d.get("response"), dict):
                ripristina_responses(s, d["response"])
            yield _sse(nome, d)
        elif t == "response.output_item.done" and isinstance(d.get("item"), dict):
            ripristina_responses(s, {"output": [d["item"]]})
            yield _sse(nome, d)
        elif t == "response.content_part.done" and isinstance(d.get("part"), dict):
            if isinstance(d["part"].get("text"), str):
                d["part"]["text"] = f(d["part"]["text"])
            yield _sse(nome, d)
        else:
            yield _sse(nome, d)


# ------------------------------------------------------------------ applicazione
def crea_app(scudo: Scudo | None = None, anthropic: str = "https://api.anthropic.com",
             openai: str = "https://api.openai.com", client: httpx.AsyncClient | None = None,
             immagini: str = "blocca", nota_oggi: bool = True, token: str | None = None,
             ner_sistema: bool = False, sessione_predefinita: str = "proxy", registro_uscite: str | None = None,
             ner_budget: int = 20000) -> Starlette:
    scudo = scudo or Scudo()
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=20.0))
    token = token or os.environ.get("SOSIA_TOKEN")

    def controlli(req: Request):
        host = (req.headers.get("host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "[::1]", "testserver"):
            raise ErroreScudo("Host non ammesso", 403)
        origine = req.headers.get("origin")
        if origine and not origine.startswith(("http://127.0.0.1", "http://localhost")):
            raise ErroreScudo("Origine non ammessa", 403)

    async def inoltra(req: Request, api: str):
        controlli(req)
        nome = req.headers.get("x-sosia-sessione", sessione_predefinita)
        s = scudo.sessione(nome)
        corpo = json.loads(await req.body() or b"{}")
        nuovo, avvisi = pseudonimizza_corpo(s, corpo, api, immagini, ner_sistema, ner_budget)
        if nota_oggi and s.istruzioni_oggi() and not req.url.path.endswith("count_tokens"):
            if api == "anthropic":
                _aggiungi_nota_anthropic(nuovo, s.istruzioni_oggi())
            else:
                _aggiungi_nota_openai(nuovo, s.istruzioni_oggi(), api)
        base = anthropic if api == "anthropic" else openai
        url = base.rstrip("/") + req.url.path + (("?" + req.url.query) if req.url.query else "")
        intest = {k: v for k, v in req.headers.items() if k.lower() not in ESCLUSE_RICHIESTA and not k.lower().startswith("x-sosia")}
        intest["accept-encoding"] = "identity"
        dati = json.dumps(nuovo, ensure_ascii=False).encode("utf-8")
        if registro_uscite:
            _annota_uscita(registro_uscite, nome, api, nuovo)
        await scudo.salva(nome)
        extra = {"x-sosia-avvisi": str(len(avvisi))}
        if nuovo.get("stream"):
            richiesta = client.build_request("POST", url, headers=intest, content=dati)
            risp = await client.send(richiesta, stream=True)
            if risp.status_code >= 400:
                corpo_err = await risp.aread()
                await risp.aclose()
                return Response(s.ripristina(corpo_err.decode("utf-8", "replace")).testo.encode("utf-8"),
                                status_code=risp.status_code, media_type=risp.headers.get("content-type"))
            gen = {"anthropic": flusso_anthropic, "chat": flusso_chat, "responses": flusso_responses}[api]

            async def corpo_flusso():
                try:
                    async for b in gen(s, risp.aiter_lines()):
                        yield b
                finally:
                    await risp.aclose()
            h = {k: v for k, v in risp.headers.items() if k.lower() not in ESCLUSE_RISPOSTA}
            h.update(extra)
            return StreamingResponse(corpo_flusso(), status_code=risp.status_code, headers=h,
                                     media_type="text/event-stream")
        risp = await client.post(url, headers=intest, content=dati)
        h = {k: v for k, v in risp.headers.items() if k.lower() not in ESCLUSE_RISPOSTA}
        h.update(extra)
        try:
            j = risp.json()
        except ValueError:
            return Response(s.ripristina(risp.text).testo, status_code=risp.status_code, headers=h)
        if req.url.path.endswith("count_tokens"):
            return JSONResponse(j, status_code=risp.status_code, headers=h)
        j = {"anthropic": ripristina_anthropic, "chat": ripristina_chat, "responses": ripristina_responses}[api](s, j)
        return JSONResponse(j, status_code=risp.status_code, headers=h)

    def gestisci(api):
        async def h(req: Request):
            try:
                return await inoltra(req, api)
            except ErroreScudo as e:
                return JSONResponse({"type": "error", "error": {"type": "sosia_error", "message": str(e)}}, status_code=e.stato)
        return h

    async def servizio(req: Request):
        """Servizio per le applicazioni integrate: {"testo", "sessione"} → pseudonimizza o ripristina. Serve il gettone locale."""
        try:
            controlli(req)
        except ErroreScudo as e:
            return JSONResponse({"errore": str(e)}, status_code=e.stato)
        if not token or not hmac.compare_digest(req.headers.get("x-sosia-token", ""), token):
            return JSONResponse({"errore": "gettone mancante o errato"}, status_code=401)
        j = await req.json()
        nome = str(j.get("sessione") or "servizio")
        if req.url.path.endswith("distruggi"):
            scudo._sessioni.pop(nome, None)
            eliminata = scudo.cassaforte.elimina(nome) if scudo.cassaforte is not None else False
            return JSONResponse({"distrutta": True, "file_eliminato": eliminata})
        s = scudo.sessione(nome)
        if req.url.path.endswith("pseudonimizza"):
            e = s.pseudonimizza(str(j.get("testo", "")))
            await scudo.salva(nome)
            return JSONResponse({"testo": e.testo, "conteggi": e.conteggi, "avvisi": e.avvisi,
                                 "nota_oggi": s.istruzioni_oggi()})
        e = s.ripristina(str(j.get("testo", "")))
        return JSONResponse({"testo": e.testo, "incerti": [{"motivo": x["motivo"], "inizio": x["inizio"], "fine": x["fine"]} for x in e.incerti]})

    async def inoltro_trasparente(req: Request):
        try:
            controlli(req)
        except ErroreScudo as e:
            return JSONResponse({"errore": str(e)}, status_code=e.stato)
        base = openai if req.url.path.startswith("/v1/chat") or req.url.path.startswith("/v1/responses") else anthropic
        url = base.rstrip("/") + req.url.path + (("?" + req.url.query) if req.url.query else "")
        intest = {k: v for k, v in req.headers.items() if k.lower() not in ESCLUSE_RICHIESTA and not k.lower().startswith("x-sosia")}
        intest["accept-encoding"] = "identity"
        risp = await client.request(req.method, url, headers=intest, content=await req.body())
        h = {k: v for k, v in risp.headers.items() if k.lower() not in ESCLUSE_RISPOSTA}
        return Response(risp.content, status_code=risp.status_code, headers=h)

    async def salute(req: Request):
        return JSONResponse({"stato": "ok", "servizio": "sosia", "ner": scudo.stato_ner})

    rotte = [
        Route("/v1/messages", gestisci("anthropic"), methods=["POST"]),
        Route("/v1/messages/count_tokens", gestisci("anthropic"), methods=["POST"]),
        Route("/v1/chat/completions", gestisci("chat"), methods=["POST"]),
        Route("/v1/responses", gestisci("responses"), methods=["POST"]),
        Route("/sosia/pseudonimizza", servizio, methods=["POST"]),
        Route("/sosia/ripristina", servizio, methods=["POST"]),
        Route("/sosia/distruggi", servizio, methods=["POST"]),
        Route("/salute", salute, methods=["GET"]),
        Route("/{resto:path}", inoltro_trasparente, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]),
    ]
    return Starlette(routes=rotte)


def _annota_uscita(file: str, sessione: str, api: str, corpo: dict):
    """Diagnostica facoltativa (--registro-uscite): che cosa è uscito davvero verso la cloud (testo GIÀ pseudonimizzato).
    Si registra l'ultimo messaggio (quello nuovo del turno), tagliato a 20.000 caratteri; il file resta locale."""
    try:
        p = Path(file)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p.stat().st_size > 20 * 1024 * 1024:
            p.replace(p.with_suffix(p.suffix + ".1"))
        ultimo = (corpo.get("messages") or [{}])[-1] if api != "responses" else {"content": corpo.get("input")}
        voce = {"quando": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "sessione": sessione, "api": api,
                "ultimo_messaggio": json.dumps(ultimo.get("content"), ensure_ascii=False)[:20000]}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(voce, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def gettone_locale(cartella: Path) -> str:
    """Gettone per gli endpoint /sosia/*: creato una volta, salvato in un file dell'utente (mai stampato)."""
    f = cartella / "gettone.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    cartella.mkdir(parents=True, exist_ok=True)
    t = secrets.token_urlsafe(32)
    f.write_text(t, encoding="utf-8")
    return t
