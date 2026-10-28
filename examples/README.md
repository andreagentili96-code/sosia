# Examples

| File | What it shows | Needs |
|---|---|---|
| `quickstart.py` | pseudonymise a letter, restore a (pretend) LLM answer, byte-for-byte round trip | nothing (no network, no model) |
| `proxy_anthropic.py` | Claude through the local proxy, streaming | `sosia proxy`, `anthropic`, an API key |
| `proxy_openai.py` | an OpenAI model through the local proxy, streaming | `sosia proxy`, `openai`, an API key |

## Invented documents (`documents/`)

Every person, company, code, address and number in these files is invented: placeholder names (Rossi, Bianchi, Verdi,
Neri, Doe), sequential phone numbers or fictional ranges, `example.com` domains, documentation IP addresses, the
classic test card number and the classic example IBAN.

| File | Format | Try |
|---|---|---|
| `lettera_avvocato.md`, `lettera_avvocato.pdf` | Italian lawyer's letter | `sosia pseudonimizza examples/documents/lettera_avvocato.pdf` |
| `cartella_clinica.txt` | Italian clinical record | `sosia pseudonimizza examples/documents/cartella_clinica.txt --fuga` |
| `verbale_cronologia.txt` | board minutes with a timeline | dates shifted by whole weeks, law dates untouched |
| `contratto.docx` | rental contract (bold runs, table, header, metadata) | edited in place, styles kept |
| `paghe.xlsx` | payroll sheet (codice fiscale, IBAN, date cells, formulas) | edited in place |
| `email.eml` | email with HTML part and attachment | headers, body and attachment |
| `crm.json` | CRM record | keys `nome`/`cognome` used as context |
| `clinic_letter_us.txt` | US clinic letter (SSN, MRN, ZIP, US dates) | English, US date convention |
| `gp_letter_uk.txt` | UK GP letter (NHS number, postcode, UK dates) | English, UK date convention |

```bash
sosia pseudonimizza examples/documents/contratto.docx --sessione demo     # -> contratto.finto.docx
sosia ripristina examples/documents/contratto.finto.docx --sessione demo -o contratto.tornato.docx
```
