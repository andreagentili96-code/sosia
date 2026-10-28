# What Sosia does NOT protect

*[Italiano](LIMITI.md)*

Sosia greatly reduces what a cloud provider sees, but it is not guaranteed anonymisation. It is pseudonymisation in
the sense of Article 4 GDPR: whoever holds the map can get back to the real data. These are the known limits of 0.6.0.

## Detection

- **What is not found is sent in clear.** On the 0.6.0 final set (80 unseen Italian and English documents, measured
  once, rules + GLiNER "auto"): codes and patterns 97.1%, names 96.5% (Italian 94.7%, English 98.4%), places 79.5%
  (Italian 82.1%, English 76.2%), precision 92.1%, exact round trip 80/80. With rules only, names drop to 89.2% and
  places to 76.2%. For sensitive documents use `--ner gliner --fuga` and review the pseudonymised text before sending.
- **Rare places.** The final set was built around hard places. Mostly missed: Welsh house and farm names without cues
  ("Ty Gwyn", "Pen y Bryn"), Italian farmsteads and hamlets written in lower case after their type, provincial roads with
  a name ("SP 22 Orgosolo-Mamoiada"), bilingual names with a slash ("Merano / Meran"), mountains, lakes and valleys,
  foreign states, US ranches and state highways.
- **Official lists only with context.** Municipality, hamlet and village names (ISTAT, OS Open Names) count only after
  a preposition, "frazione", "born in", a postcode, a province code or a house number: a small village mentioned with
  none of these cues stays in clear. This is deliberate, otherwise words like "Ponte" or "Mill" would become places
  everywhere.
- **Dates left in clear (leaks).** On the final set: 28 in 80 documents (target 0, not met). Mostly vague expressions
  ("the end of the month", "spring", "end of the quarter", "in three months"), years before 1950, years written in
  words, a month in capitals, "3rd quarter". Relative words without a document date stay relative on purpose (they do
  not reveal the date).
- **Dates shifted by mistake.** The rule is "when in doubt, shift": scores and fractions that look like dates (a "7/10"
  pain score, "3/4") and quantities that look like years are shifted (51 cases on the final set, almost all traps placed
  by the authors). The restore puts them back, but the model reads them changed.
- **Numbers without a checksum.** Passports, US driver's licences, accounts, sort codes, claim or file numbers are
  recognised only with a nearby label ("Passport No.", "Account number") or by their shape; an isolated unlabelled
  number may pass.
- **Names that are also words.** Surnames such as "Baker", "Young" or "Rose" are replaced on their own only with a cue
  nearby (title, first name, role). A lower-case name that is also a word stays out.
- **Language and date convention.** A short text can be taken for the wrong language. If an English document has no
  unambiguous date and no country cue, the UK convention `DD/MM/YYYY` is assumed; a document mixing US and UK dates is
  read with one convention only.
- **Round trip guaranteed, with one condition.** Every outgoing text is restored locally without the model and compared
  with the original: if a fake value would not come back identical, that piece is sent as a `⟦Sn⟧` placeholder. The
  guarantee covers the text sent; what the model writes anew (a rewording, a computation) comes back through the
  restore rules described below.
- **Proxy start-up.** The service answers at once with rules only; during the ~15 seconds the model takes to load,
  unknown capitalised words are replaced as a precaution (a few more false positives). If the proxy does not answer,
  the calling application must block the request: never send clear text because the shield failed.
- **GLiNER** runs on CPU only: about 1 s per 1,000 characters. Its tokenizer is rebuilt without protobuf, with NFKC
  normalisation instead of SentencePiece's internal one (identical on our test sets, possible differences on rare
  characters).
- **False positives.** In leak-proof mode, capitalised titles, drug names, brands and section names are replaced too.
  The restore puts them back, but the model works on a stranger text.
- **Law numbers.** The number of a law quoted with its date ("legge 10 dicembre 2014 n. 162") can be replaced as a
  generic code: the date stays, the number comes back on restore, but the model reads a wrong number.
- **Italian aliases in English texts.** Common English names that also appear in the Italian lists ("Michael Brown")
  can receive an Italian alias. Restoring is unaffected, but the fake text reads less naturally.
- **Health data.** By default diagnoses are only flagged, not changed: a model reading a therapy next to an unrelated
  disease gets confused. People are always replaced; with `sanitari="sostituisci"` diagnoses are changed as well.
- **Companies and amounts.** Company names are not replaced by default (`--aziende` to do it); amounts are never
  touched, because the work needs them. A rare amount can identify a case.

## Inference and rare data

- **Context remains.** Roles, jobs, rare diseases and events ("the only notary in a village of 800 people", "the
  mayor", "the winner of the 2019 competition") can identify someone even with fake names.
- **Structure remains by design.** Intervals between dates, ages, number of children, amounts, family relations (the
  same fake surname for the same family): this is what keeps quality, and it is also a fingerprint.
- **The date shift is not a strong secret.** There is one shift per session: knowing a single real date (a public
  holiday mentioned in the text, a public judgment, a document dated today) reveals all of them. This is why, by
  default, today's date is not disclosed to the model: ages arrive already computed and computations relative to today
  come back as markers evaluated locally. Limits of this choice: an age next to a birth date lets someone estimate the
  shift within a year; the model cannot chain reasoning on a result it does not know; with `--dichiara-oggi` the
  provider, which knows the time of the request, can derive the shift exactly.
- **Holidays move.** A text saying "at Christmas" next to a date reveals the shift.
- **Area codes.** The area code of a landline (06 = Rome) stays while the city changes: a small clue.
- **Recognisable fake phones.** For the US and the UK, Sosia uses the ranges reserved for fiction (555-01xx,
  07700 900xxx): anyone who knows them can tell they are fake, but they never ring a real person.

## Formats

- **Images.** Text in images, scans and photos is not protected (no OCR). The proxy blocks images by default; DOCX and
  XLSX keep them and report it; email drops attachments it cannot process.
- **PDF.** The output is a new, text-only PDF: layout, tables, signatures, forms and images are lost; extraction can
  split lines and words (a name split across lines may slip through). Scanned PDFs are rejected.
- **DOCX.** A name split across two formatting runs ("**Gio**vanni") comes back whole in the first run; computed
  fields, drawn text boxes and embedded objects are not processed.
- **XLSX.** Cached formula values stay as saved (only date cells are shifted); charts and pivot tables with caches can
  hold copies of the original data; comments and data validation are not processed.
- **Email.** Technical headers (Received, DKIM…) are removed and do not come back.

## Restore

- **Streaming.** The answer arrives with a short delay, because a tail as long as the longest fake value plus 20
  characters (40 to 160) is always held back, cut at a space.
- **Mangled aliases.** If the model inflects, translates or mangles an alias in an unexpected way, the spot is reported
  as uncertain and not restored.
- **Distant dates.** Dates outside the session window (two years around the fake dates) are not touched: a historical
  date quoted by the model stays right, but a very distant fake date computed by the model would stay fake (reported).
- **Collisions.** A text from outside the session that happens to contain an alias is "restored" by mistake. Sosia
  warns when an alias already appears in the original text.
- **Month and year without a day** computed by the model come back to the most likely correct month.

## Local security

- Whoever controls your user account can read the map: DPAPI protects against other users and against copies of the
  file on other computers, not against the user. Python cannot reliably wipe memory.
- "Secure" deletion overwrites the file, but this is not guaranteed on SSDs.
- The proxy is a local oracle: a program on your computer that uses your API key could have an alias restored. This is
  why the `/sosia/*` endpoints require a token and the proxy listens on 127.0.0.1 only.
- Linux and macOS have no DPAPI: the map is encrypted with a key derived with scrypt from `SOSIA_PAROLA`. These
  platforms are less tested than Windows.

## One-way flows

Summaries, notifications, calendars and memories that do not come back through Sosia would contain realistic fake data
that someone might take for real. In those cases placeholder redaction (`[PERSON_1]`) is safer than surrogates.
