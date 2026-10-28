"""Proxy: il fornitore finto (MockTransport) vede solo dati finti; il client riceve i dati veri, anche in streaming."""
from __future__ import annotations

import asyncio
import json

import httpx

from sosia import Configurazione
from sosia.proxy import Scudo, crea_app

TESTO = "Scrivi alla sig.ra Anna Rossi (C.F. RSSNNA81S42F205F), nata il 02/11/1981, IBAN IT60 X054 2811 1010 0000 0123 456."
VERI = ("Rossi", "RSSNNA81S42F205F", "02/11/1981", "IT60 X054")


def _app(gestore):
    visto = {}

    def fornitore(req: httpx.Request):
        corpo = json.loads(req.content)
        visto["corpo"] = corpo
        visto["intestazioni"] = dict(req.headers)
        return gestore(corpo)

    scudo = Scudo(None, Configurazione(seme=3))
    app = crea_app(scudo, client=httpx.AsyncClient(transport=httpx.MockTransport(fornitore)), token="t")
    return app, visto, scudo


def _testo_inviato(corpo) -> str:
    return json.dumps(corpo, ensure_ascii=False)


def _eco_anthropic(corpo):
    # il «modello» ripete il messaggio dell'utente: deve contenere solo dati finti
    testo = corpo["messages"][-1]["content"]
    if corpo.get("stream"):
        eventi = [("message_start", {"type": "message_start", "message": {"id": "m", "content": []}}),
                  ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})]
        for i in range(0, len(testo), 5):  # pezzi da 5 caratteri: gli alias vengono spezzati
            eventi.append(("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                   "delta": {"type": "text_delta", "text": testo[i:i + 5]}}))
        eventi += [("content_block_stop", {"type": "content_block_stop", "index": 0}),
                   ("message_stop", {"type": "message_stop"})]
        sse = "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in eventi)
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
    return httpx.Response(200, json={"id": "m", "type": "message", "role": "assistant",
                                     "content": [{"type": "text", "text": testo},
                                                 {"type": "tool_use", "id": "t", "name": "salva", "input": {"chi": testo[:40]}}],
                                     "stop_reason": "end_turn"})


def _chiama(app, percorso, corpo, stream=False):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
            if not stream:
                r = await c.post(percorso, json=corpo, headers={"x-api-key": "chiave-finta"})
                return r.status_code, r.json()
            pezzi = []
            async with c.stream("POST", percorso, json=corpo, headers={"x-api-key": "chiave-finta"}) as r:
                async for riga in r.aiter_lines():
                    pezzi.append(riga)
            return r.status_code, pezzi
    return asyncio.run(go())


def test_anthropic_non_streaming():
    app, visto, scudo = _app(_eco_anthropic)
    stato, r = _chiama(app, "/v1/messages", {"model": "x", "max_tokens": 10, "messages": [{"role": "user", "content": TESTO}]})
    assert stato == 200
    inviato = _testo_inviato(visto["corpo"])
    assert not any(v in inviato for v in VERI), "il fornitore ha visto un dato vero"
    assert "Non conosci la data di oggi" in visto["corpo"]["system"]  # la data di oggi non esce
    import datetime as dt
    assert dt.date.today().strftime("%d/%m/%Y") not in inviato
    assert "[età" in inviato  # l'età è calcolata sul PC e inviata già pronta
    assert visto["intestazioni"]["x-api-key"] == "chiave-finta"  # la chiave passa intatta
    assert r["content"][0]["text"] == TESTO
    assert "Rossi" in r["content"][1]["input"]["chi"]


def test_anthropic_streaming_con_alias_spezzati():
    app, visto, _ = _app(_eco_anthropic)
    stato, righe = _chiama(app, "/v1/messages", {"model": "x", "max_tokens": 10, "stream": True,
                                                 "messages": [{"role": "user", "content": TESTO}]}, stream=True)
    testo = "".join(json.loads(r[5:])["delta"]["text"] for r in righe
                    if r.startswith("data:") and '"text_delta"' in r)
    assert testo == TESTO


def _eco_openai(corpo):
    testo = corpo["messages"][-1]["content"]
    if corpo.get("stream"):
        righe = []
        for i in range(0, len(testo), 4):
            righe.append({"id": "c", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": testo[i:i + 4]}, "finish_reason": None}]})
        righe.append({"id": "c", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        sse = "".join(f"data: {json.dumps(r)}\n\n" for r in righe) + "data: [DONE]\n\n"
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
    return httpx.Response(200, json={"id": "c", "object": "chat.completion",
                                     "choices": [{"index": 0, "message": {"role": "assistant", "content": testo}, "finish_reason": "stop"}]})


def test_openai_chat_streaming_e_non():
    app, visto, _ = _app(_eco_openai)
    stato, r = _chiama(app, "/v1/chat/completions", {"model": "x", "messages": [{"role": "user", "content": TESTO}]})
    assert not any(v in _testo_inviato(visto["corpo"]) for v in VERI)
    assert r["choices"][0]["message"]["content"] == TESTO
    stato, righe = _chiama(app, "/v1/chat/completions", {"model": "x", "stream": True,
                                                         "messages": [{"role": "user", "content": TESTO}]}, stream=True)
    testo = ""
    for riga in righe:
        if riga.startswith("data:") and "[DONE]" not in riga:
            for ch in json.loads(riga[5:])["choices"]:
                testo += ch["delta"].get("content", "")
    assert testo == TESTO


def test_immagini_bloccate_e_origine_estranea_rifiutata():
    app, visto, _ = _app(_eco_anthropic)
    stato, r = _chiama(app, "/v1/messages", {"model": "x", "max_tokens": 10, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}}]}]})
    assert stato == 422 and "corpo" not in visto

    async def da_sito():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
            return (await c.post("/v1/messages", json={"messages": []}, headers={"origin": "https://sito-estraneo.example"})).status_code
    assert asyncio.run(da_sito()) == 403


def test_servizio_locale_richiede_gettone():
    app, _, _ = _app(_eco_anthropic)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
            senza = await c.post("/sosia/pseudonimizza", json={"testo": TESTO})
            con = await c.post("/sosia/pseudonimizza", json={"testo": TESTO, "sessione": "a"}, headers={"x-sosia-token": "t"})
            indietro = await c.post("/sosia/ripristina", json={"testo": con.json()["testo"], "sessione": "a"}, headers={"x-sosia-token": "t"})
            return senza.status_code, con.json(), indietro.json()
    s, con, indietro = asyncio.run(go())
    assert s == 401 and "Rossi" not in con["testo"] and indietro["testo"] == TESTO


def test_inoltro_trasparente_di_altri_percorsi():
    def fornitore(req):
        return httpx.Response(200, json={"percorso": req.url.path})
    from sosia.proxy import Scudo, crea_app
    app = crea_app(Scudo(None, Configurazione(seme=3)), client=httpx.AsyncClient(transport=httpx.MockTransport(fornitore)))

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
            return (await c.get("/v1/models")).json()
    assert asyncio.run(go()) == {"percorso": "/v1/models"}


def test_registro_delle_uscite_contiene_solo_dati_finti(tmp_path):
    visto = {}

    def fornitore(req):
        return _eco_anthropic(json.loads(req.content))
    from sosia.proxy import Scudo, crea_app
    reg = tmp_path / "uscite.jsonl"
    app = crea_app(Scudo(None, Configurazione(seme=3)), client=httpx.AsyncClient(transport=httpx.MockTransport(fornitore)),
                   registro_uscite=str(reg))
    _chiama(app, "/v1/messages", {"model": "x", "max_tokens": 10, "messages": [{"role": "user", "content": TESTO}]})
    testo = reg.read_text(encoding="utf-8")
    assert "ultimo_messaggio" in testo and not any(v in testo for v in VERI)
