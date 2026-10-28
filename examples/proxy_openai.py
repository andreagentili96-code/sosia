"""Ask an OpenAI model about an invented US clinic letter through the local Sosia proxy (streaming).

1. pip install -e ".[proxy]" openai
2. sosia proxy --porta 8787                 (in another terminal)
3. set OPENAI_API_KEY as usual, then:  python examples/proxy_openai.py

Set SOSIA_ESEMPIO_MODELLO to choose the model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from openai import OpenAI

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

lettera = (Path(__file__).resolve().parent / "documents" / "clinic_letter_us.txt").read_text(encoding="utf-8")
client = OpenAI(base_url="http://127.0.0.1:8787/v1")               # the API key is forwarded untouched

stream = client.chat.completions.create(
    model=os.environ.get("SOSIA_ESEMPIO_MODELLO", "gpt-4o-mini"),
    stream=True,
    messages=[{"role": "user", "content": "Who owes what to whom, and by when? Answer in 3 lines.\n\n" + lettera}],
)
for evento in stream:
    if evento.choices and evento.choices[0].delta.content:
        print(evento.choices[0].delta.content, end="", flush=True)
print()
