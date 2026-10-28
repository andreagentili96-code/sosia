# Come è fatto Sosia

## 1. Flusso

```
testo/file ──► riconoscitori ──► registrazione nella mappa ──► generatori ──► testo finto ──► cloud
                (regole, dizionari,     (sessione: reale↔finto)      (controlli validi,
                 NER facoltativo)                                      stesso formato)
risposta  ◄── ripristino (alias, valori normalizzati, date, iniziali) ◄── risposta finta
                └─► punti incerti segnalati, mai indovinati
```

Tutto gira sul PC, in Python, senza GPU; il modello NER (GLiNER) è facoltativo e si scarica a parte.

## 2. Moduli

| File | Ruolo |
|---|---|
| `sosia/sessione.py` | La `Sessione`: mappa, pseudonimizzazione, ripristino, streaming, controllo delle fughe, persistenza. |
| `sosia/riconoscitori.py` | Regole: schemi con controllo, contesto, dizionari, persone, indirizzi, città; arbitraggio delle sovrapposizioni. |
| `sosia/date.py` | Date italiane in tutti i formati comuni, spostamento componente per componente, riferimenti normativi esclusi. |
| `sosia/validatori.py` | Codice fiscale (con omocodia), P.IVA, IBAN con CIN italiano, Luhn. |
| `sosia/generatori.py` | Dati finti: CF, IBAN, P.IVA, carte, telefoni, targhe, documenti, pratiche, civici. |
| `sosia/dati.py`, `sosia/dati_en.py` | Dizionari: nomi, cognomi, comuni con codice catastale, vie, alias; carica gli estratti degli elenchi ufficiali in `sosia/dizionari/` (fonti in NOTICE). |
| `sosia/cassaforte.py` | Mappe cifrate su disco (AES-256-GCM, chiave DPAPI o scrypt), scadenza, cancellazione. |
| `sosia/formati/` | Testo/Markdown/CSV, JSON, DOCX, XLSX, PDF, email. |
| `sosia/proxy.py` | Proxy HTTP per Anthropic e OpenAI (anche streaming) e servizio locale per le applicazioni integrate. |
| `sosia/ner.py` | Aggancio facoltativo a GLiNER (consigliato) o spaCy, caricati solo da disco. |
| `sosia/cli.py` | Riga di comando. |

## 3. Riconoscimento

**Schemi con controllo** (precisione alta): codice fiscale (forma, omocodia, carattere di controllo; un CF con
controllo errato si sostituisce comunque, perché identifica lo stesso), IBAN (lunghezza del paese, mod 97; il
taglio esatto alla lunghezza del paese evita di inglobare le parole dopo), P.IVA (cifra di controllo, oppure
etichetta «P.IVA»), carte (Luhn), telefoni italiani fissi e mobili con o senza +39, email, URL, indirizzi IP,
targhe, carte d'identità elettroniche, passaporti, tessere sanitarie, CAP.

**Contesto**: numeri dopo «pratica», «fascicolo», «R.G.», «protocollo», «sinistro», «polizza», «cartella»,
«matricola», «documento n.»…; città dopo «nato a», «residente in», «con sede in», dopo un CAP o un indirizzo,
prima di una sigla di provincia «(BG)», in testa a una data «Bergamo, 20 giugno 2025»; indirizzi con
Via/Viale/Piazza/Corso… e civico.

**Persone**: titolo («Sig.ra», «Avv.», «Dott.ssa»), indizio («il sottoscritto», «paziente», «nata a», «Gentile»,
«in persona di»), etichetta («Paziente: GRECO CARMELA», «Cognome / Nome:»), dizionario (nome noto accanto a una
parola maiuscola, in entrambi gli ordini), cognomi frequenti, chi parla in una chat esportata. Esclusioni:
nomi di santi e intitolazioni («Ospedale San Giovanni», «Liceo Volta»), ragioni sociali («Rosa Verde S.r.l.»).

**Arbitraggio**: se due riconoscitori si sovrappongono vince il tipo più affidabile (CF/IBAN/email > carte/P.IVA >
documenti/telefoni > pratiche/targhe > date/indirizzi > persone > città > numeri generici), poi l'intervallo più
lungo. Una data valida vince su un «telefono» senza etichetta.

**Modalità «a prova di fuga»** (`modalita="fuga"`): ogni parola maiuscola a metà frase che non è una parola nota
diventa un nome proprio da sostituire, ogni numero lungo e ogni codice con barre è sostituito, i nomi noti si
sostituiscono anche dopo «Santa». Più falsi positivi (misurati nel banco), meno fughe. In questa modalità, se dopo
la sostituzione resta un dato originale, l'invio è bloccato (`FugaRilevata`).

**NER locale (GLiNER, `--ner gliner`)**: `urchade/gliner_multi_pii-v1` su CPU, caricato da disco senza rete
(scaricato a parte con `scripts/download_models.py`). Etichette italiane: persona, soprannome, città, paese o frazione, organizzazione, numero di
serie, numero di documento, codice identificativo, matricola. Le persone del modello entrano fra i candidati (le
particelle «LA», «De» davanti si aggregano al cognome; un nome dentro un'organizzazione si scarta), i luoghi diventano
città, i codici con almeno 5 cifre (o lettere e 3 cifre) diventano «codici» a priorità bassa (perdono contro pratiche e
documenti trovati a regole; mai anni, date o importi). Entità a cavallo di due righe scartate. Se il modello fallisce
restano le regole. Testo a finestre di ~1200 caratteri.

## 4. Coerenza

- **Nomi a livello di parola.** Ogni nome di battesimo e ogni cognome ha un alias proprio, valido per tutta la
  sessione. Ne seguono da sole le varianti: «Mario Rossi», «Rossi», «ROSSI MARIO», «Rossi's», «M. Rossi»,
  «Rossi M.», e la famiglia: «Anna Rossi» condivide il cognome finto di «Mario Rossi».
- **Genere**: l'alias di un nome femminile è femminile (dizionario, poi titolo o «nata», poi desinenza).
- **Alias scelti fra parole che non sono parole comuni** («Galimberti», non «Bianchi»), e mai fra le parole
  presenti nel testo: il ripristino non confonde «bianchi» aggettivo con un cognome.
- **Particelle conservate**: «De Luca» → «De …», così «di Bergamo» e «Di Bergamo» tornano con le maiuscole giuste.
- **Codice fiscale coerente**: se le prime sei lettere del CF corrispondono a una persona riconosciuta, il CF finto
  si costruisce con nome e cognome finti di quella persona, con la data di nascita spostata di Δ, lo stesso sesso
  e il codice catastale della città finta che ha preso il posto del luogo di nascita. Se il documento dice «nata a
  Roma il 02/11/1981», nel testo finto città, data e CF raccontano la stessa storia.
- **IBAN**: italiano con ABI noto (oppure lo stesso ABI con `iban_banca="mantieni"`), CAB e conto casuali, CIN e
  cifre di controllo ricalcolati. Esteri: stessa struttura e controllo mod 97 valido.
- **Pratiche e protocolli**: cifre nuove, lettere invariate, l'anno («4512/2026») spostato come le date.
- **Email**: la parte locale con il nome diventa quella dell'alias (`m.rossi78@…` → `f.mazzola78@…`, con lo stesso dominio pubblico);
  i domini privati diventano domini finti coerenti in tutta la sessione, quelli pubblici (gmail, libero, pec.it) restano.

## 5. Date

Spostamento Δ unico per sessione, scelto a caso fra 26 e 156 settimane indietro (multiplo di 7 per conservare il
giorno della settimana; disattivabile). Ogni data è riscritta componente per componente: giorno, mese (numero,
nome intero o abbreviato, maiuscole), anno (4 cifre, 2 cifre, «'26»), giorno della settimana, «1°».
Gestite anche le date senza anno («il 5 ottobre», anno preso dal contesto), mese e anno («ottobre 2026»),
anni in contesto («nel 2019», «esercizio 2025»). Le date dei riferimenti normativi (legge, D.Lgs., D.P.R.,
regolamento, direttiva, circolare, Gazzetta Ufficiale) non si spostano. XLSX: le celle data (numeri con formato
data) si spostano di Δ, come le costanti `DATE(…)` nelle formule.

Al ritorno ogni data dentro la finestra della sessione (date finte ± 2 anni) torna indietro di Δ: anche quelle
calcolate dal modello (scadenze, «30 giorni dopo»). Le date fuori finestra restano com'erano e sono segnalate.
La forma esatta di ogni data finta è ricordata, così «1° ottobre» torna «1° ottobre» e non «1 ottobre».

**«Oggi».** Di base la data di oggi NON va al modello, così Δ resta segreto anche
per il fornitore. Due meccanismi locali:
- *in andata*: accanto alle date di nascita («nato/nata il», «data di nascita», «classe») Sosia scrive
  «[età N anni]» calcolata con la data vera; al ritorno l'annotazione sparisce;
- *al ritorno*: il prompt di sistema (`Sessione.istruzioni_oggi()`, aggiunto dal proxy) chiede al modello di non
  indovinare e di scrivere `⟦OGGI⟧`, `⟦ETA:data⟧`, `⟦GIORNI:data⟧`, `⟦SCADENZA:data⟧` con le date del documento;
  il ripristino riporta la data alla verità (−Δ) e calcola rispetto alla data vera di oggi.
`dichiara_oggi=True` (`--dichiara-oggi`) ripristina la vecchia proposta: «Data di oggi: <oggi + Δ>» nel prompt.

## 6. Ripristino

1. **Schemi normalizzati**: nella risposta si cercano CF, IBAN, P.IVA, carte, telefoni, targhe, documenti,
   pratiche; si normalizzano (spazi, trattini, maiuscole) e si cercano fra i finti; il vero si rimette nel formato
   scelto dal modello (se scrive l'IBAN senza spazi, torna senza spazi).
2. **Alias e valori esatti**: un'unica espressione regolare con tutti gli alias (nomi, cognomi, città con CAP e
   sigla, vie con civico, aziende, email, domini), senza distinzione di maiuscole; il vero riceve le maiuscole
   usate dal modello («GALIMBERTI» → «ROSSI»).
3. **Iniziali**: «L. Galimberti» → «M. Rossi» solo se l'iniziale indica una sola persona di quella famiglia;
   altrimenti è segnalata.
4. **Date**: spostamento inverso (§5).
5. **Incerti**: una parola a distanza 1 da un alias («Galimbert», «Galimbertis»), un CF o un IBAN che differisce
   di 1–2 caratteri da un finto, un CAP o un civico non in mappa: **non** si toccano e finiscono in `Esito.incerti`.

Streaming: `RipristinoFlusso` trattiene una coda lunga quanto l'alias più lungo più un margine e la rilascia solo
quando nessuna sostituzione la attraversa. Nel proxy: Anthropic `text_delta` ripristinati al volo, `input_json_delta`
degli strumenti raccolti e ripristinati alla chiusura del blocco; OpenAI `delta.content` al volo, `tool_calls` alla
fine; Responses API `output_text.delta` al volo e oggetti finali ripristinati. I blocchi `thinking` firmati non si
toccano (contengono già i dati finti dei turni precedenti).

Nelle conversazioni il proxy fa **due passate**: la prima registra tutte le persone di tutti i messaggi, la seconda
sostituisce; così un «Rossi» nel primo messaggio è coperto anche se «Mario Rossi» compare solo dopo.

## 7. Formati

| Formato | Come | Conservato |
|---|---|---|
| Testo, Markdown, CSV | testo intero; nel CSV le colonne Nome/Cognome registrano le persone | tutto |
| JSON | valori stringa; chiavi `nome`/`cognome`/`citta` usate come contesto | struttura, numeri |
| DOCX | XML modificato in posto: paragrafo ricomposto, trasformato, ridistribuito nei run | stili, tabelle, immagini, intestazioni, note, commenti, revisioni, metadati (autore sostituito) |
| XLSX | stringhe condivise e in linea, formule, celle data, codici sotto «Matricola», nomi dei fogli, metadati; intestazioni di colonna come contesto | formattazione, grafici, immagini (senza openpyxl) |
| PDF | estrazione del testo (pypdf) e PDF nuovo solo testo | solo il testo |
| Email (.eml) | intestazioni (data spostata), testo, HTML per blocchi, allegati testuali/DOCX/XLSX/PDF; via le intestazioni tecniche | struttura MIME |

## 8. Sicurezza

- Mappa in memoria durante l'uso; su disco solo cifrata: AES-256-GCM, chiave casuale protetta con DPAPI
  (`CryptProtectData`, utente corrente) oppure scrypt (N=2^15) da `SOSIA_PAROLA`. Intestazione (id, scadenza,
  metodo) autenticata come AAD: non si allunga la scadenza senza la chiave. Scaduta → file sovrascritto e
  cancellato al primo accesso; `sosia sessioni --pulisci`.
- Registri: solo conteggi per tipo e numero di avvisi. Nessun valore originale né finto.
- Controllo prima dell'invio: ogni dato rilevato o registrato viene cercato (normalizzato) nel testo finto.
- Proxy: solo 127.0.0.1; Host e Origin controllati; chiavi API inoltrate senza essere lette; `/sosia/*`
  protetti da gettone casuale salvato nel profilo utente (mai stampato), perché ripristinare equivale a decifrare.

## 9. Integrazione in altre applicazioni

Due modi, entrambi locali:

1. **Proxy fra l'applicazione e la cloud** (consigliato quando c'è un viaggio di ritorno): l'applicazione avvia
   `python -I -m sosia proxy --porta 8787 …` e imposta `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` verso 127.0.0.1.
   Se il proxy non risponde, l'applicazione deve decidere cosa fare (bloccare l'invio o usare una riserva a
   segnaposto): mai inviare testo in chiaro per un guasto dello scudo.
2. **Servizio locale** `/sosia/pseudonimizza`, `/sosia/ripristina`, `/sosia/distruggi`, protetto da un gettone
   casuale (`SOSIA_TOKEN`), per le applicazioni che costruiscono da sole la richiesta.

Attenzione ai flussi **senza ritorno** (riepiloghi, notifiche, calendari, memorie): lì dati finti realistici
verrebbero letti come veri. In quei casi un oscuramento a segnaposto (`[PERSONA_1]`) è più sicuro dei surrogati.
