"""Summarise an invented clinical record with Claude through the local Sosia proxy (streaming).

1. pip install -e ".[proxy]" anthropic
2. sosia proxy --porta 8787                 (in another terminal; add --ner gliner if you downloaded the model)
3. set ANTHROPIC_API_KEY as usual, then:  python examples/proxy_anthropic.py

The cloud receives surrogates only; the text printed here already contains the real (invented) data again.
Set SOSIA_ESEMPIO_MODELLO to choose another model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import anthropic

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

documento = (Path(__file__).resolve().parent / "documents" / "cartella_clinica.txt").read_text(encoding="utf-8")
client = anthropic.Anthropic(base_url="http://127.0.0.1:8787")    # the API key is forwarded untouched

with client.messages.stream(
    model=os.environ.get("SOSIA_ESEMPIO_MODELLO", "claude-sonnet-4-5"),
    max_tokens=700,
    messages=[{"role": "user", "content": "Riassumi questa cartella in 5 punti, con nomi, date ed età:\n\n" + documento}],
) as stream:
    for testo in stream.text_stream:
        print(testo, end="", flush=True)
print()
