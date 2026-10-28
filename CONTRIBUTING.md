# Contributing / Contribuire

Thanks for your interest! Sosia is young (0.x). The code, comments and identifiers are in Italian, because the first
target was Italian documents (codice fiscale, IBAN, partita IVA, Italian date formats); English (US/UK) came next.
Issues and pull requests in English or Italian are both welcome.

## Ground rules

1. **No real personal data, ever** — not in code, tests, issues, screenshots or logs. Use invented data: placeholder
   names (Mario Rossi, Jane Doe), reserved domains (`example.com`, `.test`), fictional phone ranges (US 555-01xx,
   UK 07700 900xxx) and obviously fake numbers.
2. Every recogniser change needs a test in `tests/` and a short note in the PR on what it fixes and what it could break
   (false positives matter as much as misses).
3. Do not tune rules on a document set and then report numbers on the same set: measure on documents nobody looked at
   while writing the rules, and say so in the PR.
4. Nothing may call the network except the proxy forwarding to the configured provider. Models are loaded only from
   disk (`HF_HUB_OFFLINE=1`); downloads happen only in `scripts/download_models.py`, on purpose.
5. Logs contain counts only, never original or fake values.

## Development setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[test,xlsx]"
python -m pytest -q
```

On Linux and macOS set `SOSIA_PAROLA` (any passphrase) for the encrypted vault used by some tests.
GLiNER is optional: `pip install -e ".[ner-gliner]"`, then `python scripts/download_models.py`. The tests marked
`gliner` run only when the model is present; everything else runs without it.

The official-list extracts in `sosia/dizionari/` are rebuilt by `scripts/build_dictionaries.py` from the original files
(sources, licences and SHA-256 in the script, in `NOTICE` and in `sosia/dizionari/FONTI.json`).

## Contribuire (italiano)

Nessun dato personale vero, mai. Ogni modifica ai riconoscitori va con una prova in `tests/` e con una nota su cosa
migliora e cosa può peggiorare. Le misure si fanno su documenti che nessuno ha guardato mentre scriveva le regole.
