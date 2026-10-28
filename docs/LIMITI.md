# Cosa Sosia NON protegge

*[English](LIMITATIONS.md)*

Sosia riduce molto ciò che vede il fornitore in cloud, ma non è un'anonimizzazione garantita. È pseudonimizzazione
nel senso dell'art. 4 del GDPR: chi tiene la mappa può tornare ai dati veri. Questi sono i limiti noti della 0.6.0.

## Riconoscimento

- **Ciò che non si trova parte in chiaro.** Sul set finale della 0.6.0 (80 documenti italiani e inglesi mai visti,
  misurati una sola volta, regole più GLiNER «auto»): codici e schemi 97,1%, nomi 96,5% (italiano 94,7%, inglese
  98,4%), luoghi 79,5% (italiano 82,1%, inglese 76,2%), precisione 92,1%, andata e ritorno identici 80 su 80.
  Con le sole regole i nomi scendono all'89,2% e i luoghi al 76,2%. Per i documenti delicati: `--ner gliner --fuga` e una rilettura del
  testo finto prima dell'invio.
- **Luoghi rari.** Il set finale era costruito apposta su luoghi difficili. Restano fuori soprattutto: nomi di case e
  fattorie gallesi senza indizi («Ty Gwyn», «Pen y Bryn»), cascine, poderi e borgate scritti in minuscolo dopo il tipo,
  strade provinciali con il nome («SP 22 Orgosolo-Mamoiada»), nomi bilingui con la barra («Merano / Meran»), montagne,
  laghi e valli, stati esteri, ranch e statali americane.
- **Elenchi ufficiali solo con un contesto.** I nomi di comuni, frazioni e villaggi (ISTAT, OS Open Names) valgono
  solo dopo una preposizione, «frazione», «nato a», un CAP, una sigla di provincia o un numero civico: un paese piccolo
  citato senza nessuno di questi indizi resta in chiaro. È voluto: altrimenti «Ponte» o «Re» diventerebbero luoghi
  ovunque.
- **Date lasciate in chiaro (fughe).** Sul set finale: 28 in 80 documenti (obiettivo 0, non raggiunto). Sono soprattutto
  espressioni vaghe («fine del mese», «in primavera», «fine trimestre», «fra tre mesi»), anni prima del 1950, anni in
  lettere, un mese in maiuscolo («SETTEMBRE»), «3rd quarter». Le parole relative senza una data del documento restano
  relative di proposito (non rivelano la data).
- **Date spostate per errore.** La regola è «nel dubbio si sposta»: punteggi e frazioni che sembrano date («7/10» del
  dolore, «3/4») e quantità che sembrano anni vengono spostati (51 casi sul set finale, quasi tutti trappole messe
  apposta dagli autori). Il ripristino li rimette a posto, ma il modello li legge cambiati.
- **Numeri senza controllo.** Passaporti, patenti americane, conti, sort code, numeri di sinistro o di cartella si
  riconoscono solo con un'etichetta vicina («Passport No.», «Account number», «pratica n.») o per la forma; un numero
  isolato senza etichetta può passare.
- **Nomi che sono anche parole.** Cognomi come «Baker», «Young», «Rose» o «Rosa» da soli si sostituiscono solo con un
  indizio vicino (titolo, nome, ruolo). Un nome in minuscolo che è anche una parola resta fuori.
- **Lingua e convenzione delle date.** Un testo breve può essere preso per la lingua sbagliata. Se un documento inglese
  non ha date inequivocabili né indizi del paese, si assume la convenzione britannica `GG/MM/AAAA`; un documento che
  mescola date americane e britanniche viene letto con una sola convenzione.
- **Ritorno garantito, a una condizione.** Ogni testo in uscita viene ripristinato sul computer senza modello e
  confrontato con l'originale: se un dato finto non tornerebbe identico, quel pezzo parte come segnaposto `⟦Sn⟧`. La
  garanzia vale per il testo inviato; ciò che il modello scrive di nuovo (una riformulazione, un calcolo) torna con le
  regole del ripristino descritte sotto.
- **Avvio del proxy.** Il servizio risponde subito con le sole regole; nei circa 15 secondi di caricamento del modello
  le parole maiuscole sconosciute si sostituiscono per prudenza (qualche falso positivo in più). Se il proxy non
  risponde, l'applicazione che lo usa deve bloccare l'invio: mai mandare testo in chiaro per un guasto dello scudo.
- **GLiNER** gira solo su CPU: circa 1 s ogni 1000 caratteri. Il tokenizzatore è ricostruito senza protobuf, con la
  normalizzazione NFKC al posto di quella interna di SentencePiece (identico sui banchi di prova, possibili differenze
  su caratteri rari).
- **Falsi positivi.** In modalità «a prova di fuga» si sostituiscono anche titoli in maiuscolo, farmaci, marche e nomi
  di sezioni. Il ripristino li rimette a posto, ma il modello lavora su un testo più strano.
- **Dati sanitari.** Per default le patologie sono solo segnalate, non cambiate: un modello che legge una terapia con
  una malattia che non c'entra si confonde. Le persone sono comunque sostituite; con `sanitari="sostituisci"` si cambia
  anche la patologia.
- **Aziende e importi.** Le ragioni sociali non si sostituiscono per default (`--aziende` per farlo); gli importi non
  si toccano, perché servono al lavoro. Un importo raro può identificare una pratica.

## Inferenze e dati rari

- **Il contesto resta.** Ruoli, professioni, malattie rare, eventi («l'unico notaio di un paese di 800 abitanti»,
  «il sindaco», «la vincitrice del concorso del 2019») possono identificare anche con nomi finti.
- **La struttura resta per scelta.** Intervalli fra le date, età, numero di figli, importi, relazioni familiari (lo
  stesso cognome finto per la stessa famiglia): è ciò che conserva la qualità, ed è anche un'impronta.
- **Lo spostamento delle date non è un segreto forte.** È uno solo per tutta la sessione: basta conoscere una data vera
  (una festa nazionale citata, una sentenza pubblica, un documento datato oggi) per ricavarle tutte. Per questo, di base,
  la data di oggi non è dichiarata al modello: le età arrivano già calcolate e i calcoli rispetto a oggi tornano come
  marcatori calcolati sul computer. Limiti di questa scelta: l'età accanto a una data di nascita permette di stimare lo
  spostamento a meno di un anno; il modello non può ragionare a catena su un risultato che non conosce; con
  `--dichiara-oggi` il fornitore, che conosce l'ora della richiesta, ricava lo spostamento esattamente.
- **Feste e ricorrenze cambiano data.** Un testo che dice «a Natale» accanto a una data mostra lo spostamento.
- **Prefissi telefonici.** Il prefisso di un fisso (06 = Roma) resta mentre la città cambia: un piccolo indizio.
- **Telefoni finti riconoscibili.** Per Stati Uniti e Regno Unito si usano le serie riservate alla finzione
  (555-01xx, 07700 900xxx): chi le conosce capisce che sono finti, ma non chiamano nessuno.

## Formati

- **Immagini.** Testo nelle immagini, scansioni e foto non sono protetti (niente OCR). Il proxy blocca le immagini per
  default; DOCX e XLSX le lasciano dentro e lo segnalano; l'email toglie gli allegati non trattabili.
- **PDF.** Si ottiene un PDF nuovo solo testo: impaginazione, tabelle, firme, moduli e immagini si perdono; l'estrazione
  può spezzare righe e parole (un nome spezzato a capo può sfuggire). I PDF scansionati sono rifiutati.
- **DOCX.** Un nome spezzato fra due formattazioni («**Gio**vanni») torna intero nella prima; campi calcolati, caselle
  di testo disegnate e oggetti incorporati non sono trattati.
- **XLSX.** I valori in cache delle formule restano quelli salvati (si spostano solo quelli delle celle data); grafici
  e tabelle pivot con cache possono contenere copie dei dati originali; commenti e convalide non sono trattati.
- **Email.** Le intestazioni tecniche (Received, DKIM…) sono tolte e non tornano.

## Ripristino

- **Streaming.** La risposta esce con un piccolo ritardo, perché si trattiene sempre una coda lunga quanto il dato
  finto più lungo più 20 caratteri (da 40 a 160), tagliata a uno spazio.
- **Alias storpiati.** Se il modello declina, traduce o storpia un alias in modo non previsto, il punto è segnalato fra
  gli incerti e non ripristinato.
- **Date lontane.** Le date fuori dalla finestra della sessione (due anni attorno alle date finte) non si toccano: una
  data storica citata dal modello resta giusta, ma una data finta molto lontana calcolata dal modello resterebbe finta
  (segnalata).
- **Collisioni.** Un testo che arriva da fuori della sessione e contiene per caso un alias viene «ripristinato» per
  errore. Sosia avvisa quando un alias compare già nel testo originale.
- **Mese e anno senza giorno** calcolati dal modello tornano al mese corretto più probabile.

## Sicurezza locale

- Chi ha accesso al tuo utente ha accesso alla mappa: DPAPI protegge da altri utenti e da copie del file su altri
  computer, non dall'utente stesso. Python non può azzerare con certezza la memoria.
- La cancellazione «sicura» del file sovrascrive i byte, ma su SSD non è garantita.
- Il proxy è un oracolo locale: un programma sul computer che usa la tua chiave API può farsi ripristinare un alias.
  Per questo gli endpoint `/sosia/*` richiedono un gettone e il proxy ascolta solo su 127.0.0.1.
- Su Linux e macOS non c'è DPAPI: la mappa si cifra con una chiave derivata con scrypt da `SOSIA_PAROLA`. Queste
  piattaforme sono meno provate di Windows.

## Flussi senza ritorno

Riepiloghi, notifiche, calendari e memorie che non tornano attraverso Sosia conterrebbero dati finti realistici che
qualcuno potrebbe prendere per veri. In quei casi un oscuramento a segnaposto (`[PERSONA_1]`) è più sicuro dei
surrogati.
