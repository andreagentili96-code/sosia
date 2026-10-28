<div align="center">

# Sosia

**Pseudonimizzazione realistica e reversibile per gli LLM: i tuoi dati non escono, le risposte tornano vere.**

[![CI](https://github.com/OWNER/sosia/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/sosia/actions/workflows/ci.yml)
[![Licenza: Apache-2.0](https://img.shields.io/badge/licenza-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
![Tutto in locale su CPU](https://img.shields.io/badge/gira-100%25%20in%20locale%20%C2%B7%20CPU-brightgreen.svg)

*[Read in English](README.md)*

</div>

Sosia si mette fra te (o la tua applicazione) e un LLM in cloud. Prima che una richiesta esca dal computer sostituisce
i dati personali con **dati finti realistici e coerenti fra loro**; quando arriva la risposta **rimette i dati veri**,
anche in streaming. Il modello legge un documento che ha ancora senso (codici fiscali validi, IBAN validi, la stessa
persona chiamata sempre allo stesso modo, la stessa linea temporale) e non una pagina piena di `[PERSONA_1]`.

![Prima e dopo: una lettera italiana inventata, ciò che riceve l'LLM in cloud, la sua risposta e la risposta ripristinata](docs/before-after.svg)

## Perché Sosia

- **Surrogati realistici invece di `[OSCURATO]`.** Nomi, luoghi, codici e date diventano valori plausibili dello stesso
  tipo e formato, così l'LLM ragiona ancora sul documento. Un alias per ogni nome e per ogni cognome tiene coerenti
  «Mario Rossi», «ROSSI MARIO», «M. Rossi» e «Rossi M.»; i familiari condividono il cognome finto.
- **Codici validi e coerenti fra loro.** Il codice fiscale finto si ricostruisce dal nome finto, dallo stesso sesso,
  dalla data di nascita spostata e dal codice catastale del luogo di nascita finto; IBAN (CIN italiano e mod 97) e
  partita IVA hanno le cifre di controllo giuste; SSN e ITIN americani, numeri NHS e National Insurance britannici e
  codici ABA conservano formati e controlli validi.
- **Date spostate di settimane intere.** Tutte le date di una sessione si spostano dello stesso numero di settimane:
  ordine, intervalli e giorni della settimana restano uguali (una scadenza di domenica resta di domenica). I riferimenti
  a leggi e decreti non si toccano.
- **Età e scadenze calcolate in locale, senza rivelare la data di oggi.** Sosia annota le età prima dell'invio e fa
  scrivere al modello dei marcatori (`⟦OGGI⟧`, `⟦ETA:…⟧`, `⟦SCADENZA:…⟧`) che si calcolano sul tuo computer: il
  fornitore non può ricavare lo spostamento delle date dall'ora della richiesta.
- **Ripristino identico byte per byte, controllato in automatico.** Ogni testo in uscita viene ripristinato sul computer
  senza il modello e confrontato con l'originale; ciò che non tornerebbe identico parte come segnaposto reversibile.
  Al ritorno Sosia gestisce anche alias riscritti, iniziali, formati cambiati e date calcolate dal modello; i punti
  incerti vengono segnalati, mai indovinati.
- **Streaming.** Il ripristino trattiene solo una coda breve, così un dato non esce mai a metà: risultato identico su
  320 documenti su 320 tagliati a pezzi casuali da 1 a 12 caratteri.
- **Proxy compatibile con le API di Anthropic e OpenAI.** Basta puntare `ANTHROPIC_BASE_URL` o `OPENAI_BASE_URL` sul
  proxy: `/v1/messages`, `/v1/chat/completions` e `/v1/responses`, con streaming SSE e argomenti degli strumenti.
- **Documenti, non solo stringhe.** TXT, Markdown, CSV, JSON, **DOCX** e **XLSX** modificati in posto (stili, tabelle,
  formule e celle data conservati), **PDF** (in uscita solo testo) ed **email** (`.eml`, allegati compresi).
- **Tutto in locale.** Solo CPU, modello NER facoltativo caricato dal disco, nessuna telemetria. La mappa fra dati veri e
  finti non lascia mai il computer: è cifrata (AES-256-GCM, chiave protetta con DPAPI di Windows o derivata con scrypt)
  e scade.
- **Italiano e inglese (USA e Regno Unito).** Lingua riconosciuta per testo, convenzione delle date americana o
  britannica per documento, documenti misti italiano e inglese; elenchi ufficiali di nomi e luoghi (ISTAT, OS Open
  Names, ONS, Census USA, Wikidata).
- **Pochi millisecondi per messaggio.** Da +5 a +11 ms sul primo token dei messaggi brevi, circa +0,1 s su una prima
  richiesta con 80.000 caratteri di contesto (CPU, misurato attraverso il proxy).

## Confronto

Dati controllati sulla documentazione pubblica a ottobre 2026. «—» significa non offerto o non trovato nella
documentazione pubblica.

| | **Sosia** | [Presidio](https://github.com/data-privacy-stack/presidio) (+ [LiteLLM](https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2)) | [LLM Guard](https://github.com/protectai/llm-guard) | [Limina (Private AI)](https://docs.private-ai.com/introduction) | [Tonic Textual](https://docs.tonic.ai/textual/dataset-files/dataset-file-types.md) | [OpenMed](https://github.com/maziyarpanahi/openmed) | [Latet](https://github.com/Latet-AI/latet) |
|---|---|---|---|---|---|---|---|
| Sostituzione | surrogati realistici con controlli validi | segnaposto, hash, maschera, cifratura (operatori personalizzabili) | segnaposto o valori Faker | segnaposto o sintetici (beta) | sintetici o oscuramento | segnaposto, hash o surrogati Faker | falsi della stessa forma |
| Codice fiscale coerente con nome, data e luogo finti | **sì** | riconosciuto, non generato | — | — | — | CF casuale | riconosciuto |
| Reversibile | **sì**, anche con le riscritture del modello | con cifra e decifra; LiteLLM ripristina i segnaposto | sì (vault) | — | — | vault dei surrogati | sì |
| Spostamento delle date | **settimane intere** (giorno della settimana conservato) | — | — | — | sì, in giorni | sì, in giorni (per paziente) | — |
| «Oggi», età e scadenze calcolati in locale | **sì** | — | — | — | — | — | — |
| Proxy per le API degli LLM con streaming | **sì** (Anthropic, OpenAI, strumenti) | con LiteLLM | — | — | — | — | sì (agenti di programmazione) |
| Formati | txt, md, csv, json, docx, xlsx, pdf (testo), eml | testo, dati strutturati, immagini | testo | testo, PDF, immagini, audio | il più ampio (docx, xlsx, pdf, pptx, immagini, eml…) | documenti | PDF segnalati o bloccati |
| OCR e immagini | — | **sì** | — | **sì** | **sì** | — | — |
| Lingue | italiano, inglese (USA e UK) | molte | inglese, cinese | oltre 50 | oltre 50 | 35 | diverse |
| Licenza | Apache-2.0 | MIT | MIT (archiviato) | proprietaria | proprietaria | Apache-2.0 | Sustainable Use (non OSI) |
| Tutto sul tuo computer | **sì**, CPU | sì | sì | container on-prem (a pagamento) | — | sì | sì |

Dove gli altri sono avanti: Presidio, Limina e Tonic gestiscono OCR, immagini e molte più lingue; OpenMed copre 35
lingue per i testi clinici; Presidio e LiteLLM sono maturi e molto diffusi. La nicchia di Sosia sono i surrogati fedeli
e reversibili per documenti italiani e inglesi davanti alle API degli LLM.

## Avvio rapido

```bash
git clone https://github.com/OWNER/sosia.git && cd sosia
pip install -e ".[proxy,pdf,xlsx]"
python examples/quickstart.py
```

Non servono modelli né rete: le sole regole gestiscono codici, date, indirizzi e la maggior parte dei nomi. Python 3.11
o successivo. La piattaforma di riferimento è Windows; su Linux e macOS imposta `SOSIA_PAROLA` con una frase segreta per
la mappa cifrata.

### Python

```python
from sosia import Sessione

s = Sessione()                                  # una sessione = una mappa coerente
finto = s.pseudonimizza(documento)              # finto.testo va alla cloud
risposta = chiama_il_tuo_llm(finto.testo, system=s.istruzioni_oggi())
vero = s.ripristina(risposta)                   # vero.testo; vero.incerti = punti non ripristinati con certezza

f = s.flusso()                                  # ripristino in streaming
for pezzo in stream:
    print(f.scrivi(pezzo), end="")
print(f.chiudi())
```

### Proxy (SDK di Anthropic e OpenAI, agenti da riga di comando)

```bash
sosia proxy --porta 8787                          # con --ner gliner usa anche il modello NER locale
set ANTHROPIC_BASE_URL=http://127.0.0.1:8787      # Linux e macOS: export ANTHROPIC_BASE_URL=...
set OPENAI_BASE_URL=http://127.0.0.1:8787/v1
```

```python
import anthropic

client = anthropic.Anthropic(base_url="http://127.0.0.1:8787")   # la chiave API passa intatta e non viene salvata
r = client.messages.create(model="claude-sonnet-4-5", max_tokens=800,
                           messages=[{"role": "user", "content": "Riassumi questa lettera:\n" + lettera}])
print(r.content[0].text)                                           # nomi, codici e date veri sono tornati
```

Il proxy ascolta solo su 127.0.0.1 e rifiuta gli `Origin` dei browser e gli `Host` estranei. Le immagini sono bloccate
per default (`--immagini lascia` le fa passare senza protezione); i PDF in base64 diventano testo pseudonimizzato.
`--date nascita` sposta solo le date di nascita, per gli agenti che lavorano con calendari veri. Altro in
[examples/](examples/).

### Riga di comando e file

```bash
sosia pseudonimizza contratto.docx --sessione pratica-42      # -> contratto.finto.docx
sosia ripristina risposta.md --sessione pratica-42            # tornano i dati veri
sosia pseudonimizza referto.pdf --fuga                        # modalità «a prova di fuga»: nel dubbio sostituisce
sosia sessioni --pulisci                                      # cancella le mappe scadute
```

### NER locale facoltativo (GLiNER)

Il modello non è nel repository e Sosia non scarica mai nulla mentre lavora. Si scarica una volta, di proposito:

```bash
pip install -e ".[ner-gliner]" huggingface_hub
python scripts/download_models.py        # urchade/gliner_multi_pii-v1 (Apache-2.0) + tokenizer di mdeberta-v3-base (MIT)
sosia proxy --ner gliner
```

GLiNER gira su CPU (circa 1,2 GB, circa 15 s di caricamento in sottofondo) e aggiunge i nomi rari e stranieri che le
regole non conoscono. Nel proxy lavora solo sulle frasi con parole maiuscole sconosciute.

## Misure

Tutti i documenti di prova sono inventati. Li hanno scritti autori indipendenti (generati con LLM, ognuno con il suo
elenco dei dati attesi) che non hanno mai visto il codice; prima dell'uso ogni set viene registrato con un'impronta e
cifrato, così non si può leggere durante lo sviluppo, e si misura **una sola volta**. Le regole si tarano solo sui set
già usati.

**Sosia 0.6.0, set finale di 80 documenti mai visti** (40 italiani, 40 inglesi USA e UK), regole più GLiNER «auto»:

| Misura | Risultato |
|---|---|
| Andata e ritorno identici (byte per byte) | **80/80** |
| Ripristino dopo una riscrittura simulata del modello | **99,7%** (644/646), nessun alias rimasto |
| Codice fiscale, IBAN, partita IVA, email | **100%** (24/24, 23/23, 12/12, 55/55) |
| Telefoni | 98,4% (124/126) |
| Tutti i codici e gli schemi | 97,1% (430/443) |
| Nomi e cognomi | **96,5%** (655/679): italiano 94,7%, inglese 98,4% |
| Luoghi e indirizzi (set costruito sui luoghi rari) | 79,5% (605/761) |
| Precisione | 92,1% |
| Linea temporale (ogni data letta e spostata esattamente) | 89,2% |

**Qualità con un modello vero.** Tre documenti riassunti da Claude con e senza Sosia (9 chiamate): dopo il ripristino
i riassunti avevano giusti 16 cognomi su 16 e 20 date su 20, contro 16 su 16 e 19 su 20 senza lo scudo.

**Latenza** (CPU, streaming, tempo aggiunto al primo token, mediana di 5 prove):

| Caso | Aggiunto |
|---|---|
| Messaggio breve in chat | da +5 a +11 ms |
| Prima richiesta con circa 80.000 caratteri di contesto | +109 ms |
| Documento di 2.500 caratteri | +55 ms |
| PDF di 23.700 caratteri | +435 ms |
| Ripristino in streaming di una risposta di 6.000 caratteri | circa 5 ms per pezzo |

Il set finale è stato costruito apposta sui luoghi difficili (frazioni minuscole, nomi gallesi e gaelici di case e
fattorie, contee e strade rurali americane): è lì che Sosia oggi è più debole. Vedi i limiti qui sotto.

## Prossimi passi e limiti noti

Sosia **riduce** ciò che vede il fornitore in cloud: è pseudonimizzazione, **non** anonimizzazione, e non garantisce
la conformità. L'elenco completo e onesto è in [docs/LIMITI.md](docs/LIMITI.md) ([English](docs/LIMITATIONS.md)).
In breve:

- Ciò che non viene riconosciuto parte in chiaro (vedi i numeri sopra): per i documenti delicati usa
  `--ner gliner --fuga` e rileggi il testo pseudonimizzato prima dell'invio.
- Il contesto può identificare comunque una persona (un mestiere raro, un paese piccolo, un fatto unico).
- Uno spostamento delle date per sessione: chi conosce una sola data vera le ricava tutte.
- Espressioni di tempo vaghe («fine trimestre», «in primavera») e anni molto vecchi possono restare in chiaro.
- Niente OCR: PDF scansionati e immagini non sono gestiti; il PDF in uscita è solo testo.
- La mappa locale è leggibile da chi controlla il tuo account utente.
- La piattaforma di riferimento è Windows; Linux e macOS usano la cassaforte scrypt e sono meno provati.

Prossimi passi: luoghi rari (nomi di case e fattorie britanniche, toponimi gallesi e gaelici, indirizzi rurali
americani), altre espressioni di data, un pacchetto su PyPI, nomi inglesi per l'API, integrazioni con Presidio e
LiteLLM, altre lingue. Note di progetto: [docs/DESIGN.md](docs/DESIGN.md).

## Casi d'uso

- **Studi legali**: diffide, atti, contratti e provvedimenti; nomi, codici fiscali, IBAN e numeri di pratica restano
  sul computer, mentre il modello calcola comunque le scadenze, che tornano come date vere.
- **Sanità**: lettere di dimissione e diari clinici; pazienti, familiari e medici sostituiti, date spostate in modo
  coerente così la storia clinica resta leggibile; le patologie sono segnalate ma lasciate per default (cambiarle
  confonde il modello). È uno strumento di supporto, non un dispositivo medico, e non sostituisce la valutazione
  d'impatto.
- **Risorse umane e paghe**: buste paga e fogli dei dipendenti in XLSX; nomi, codici fiscali, IBAN e date di nascita
  sostituiti in posto, con formule e formattazione conservate.
- **Commercialisti e consulenti**: fatture, lettere del fisco, estratti conto; partite IVA e IBAN validi, persone e
  società coerenti per tutta la sessione.

## Contribuire

Segnalazioni e pull request sono benvenute, in italiano o in inglese. Mai dati personali veri: né nel codice, né nelle
prove, né nelle segnalazioni o nei registri. Vedi [CONTRIBUTING.md](CONTRIBUTING.md) e, per le vulnerabilità,
[SECURITY.md](SECURITY.md). Se Sosia ti è utile, una ⭐ aiuta altri a trovarlo.

## Licenza

[Apache-2.0](LICENSE). Dati e modelli di terzi: [NOTICE](NOTICE) (ISTAT CC BY 4.0, OS e ONS con Open Government
Licence v3.0, Census USA di pubblico dominio, Wikidata CC0; GLiNER Apache-2.0 e mDeBERTa MIT, non inclusi).
