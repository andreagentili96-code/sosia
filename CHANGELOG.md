# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

- First public release on GitHub: bilingual README with comparison and benchmark, English and Italian limitations,
  examples (invented documents, library, proxy), `scripts/download_models.py` for the optional GLiNER model,
  `scripts/build_dictionaries.py` to rebuild the official-list extracts, optional GLiNER tests, CI on Windows, Linux
  and macOS. The default model folder is now `$SOSIA_MODELLI` or the user's local data folder.
- The benchmark documents are kept outside the repository, so that future measurements stay blind.
- CLI: no longer fails when the console or pipe encoding cannot print `⟦` (cp1252 on Windows); test added.

## [0.6.0] - 2026-10-28

Official lists, used only with context.

### Added
- Extracts of official lists in `sosia/dizionari/` (ISTAT municipalities and localities, OS Open Names settlements and
  roads without a suffix, ONS first names, US Census 2010 surnames, Wikidata Italian names and surnames), rebuilt by
  `scripts/build_dictionaries.py`, which checks the SHA-256 of the downloaded files; attributions in NOTICE, hashes in
  `sosia/dizionari/FONTI.json`, integrity test in `tests/test_dizionari_060.py`.
- Places: ISTAT names only after "frazione", "località", "nato a", "residente a", "comune di", a CAP or before a province
  code (municipalities also after a plain preposition); municipalities in capitals in headers; British villages only with
  a preposition, a comma or a postcode; roads without a suffix with a house number ("8 Deansgate,") or at the start of an
  address line; house and farm names in an address ("Rose Cottage", "The Old Rectory", "Croft 7", "Ty Gwyn" on its own
  line before the postcode); US counties, townships, reservations; rural routes, PO boxes, county roads and highways (only
  the digits change); Italian country addresses (strada vicinale/comunale/provinciale, cascina, podere, masseria, borgata).
- Dates: quarters without a year ("second quarter", "q1", "3rd quarter", "terzo trimestre"), Italian months in capitals,
  "decreto del 10 maggio 2023" (a court decree) is no longer taken for a law date.

### Fixed
- Place sequences: "Vallo della Lucania" stopped at "Vallo del".
- `norm()` fast path for ASCII strings: startup with the larger lists +0.3 s instead of +0.8 s.

### Measured (final sealed set 5, once, 80 new documents focused on rare places)
- Round trip 80/80, restore after rewrite 99.7%, timeline 89.2%, date leaks 28, dates shifted by mistake 51, codes 97.1%,
  names 96.5%, places 79.5%, precision 92.1%. Same 320 development documents, rules only: places 94.1% → 96.7%, names
  92.8% → 93.1%, precision 95.2% → 94.8%. Latency unchanged (long PDF +435 ms). Real Claude test: 9 calls, about
  0.59 USD, with the shield 16/16 surnames and 20/20 dates.

## [0.5.0] - 2026-10-27

Dates first ("when in doubt, shift"), more names and places, long PDFs faster than 0.2.0, streaming restore guaranteed.

### Added
- Dates: separate measures of leaks (dates left in clear) and dates shifted by mistake. Ambiguous forms are shifted:
  US day/month without a year at the start of a ledger line ("02/03  Direct deposit"), day/month invalid in the document
  convention ("8/29" in a British text), month names after more contexts ("each June", "mid-April", "(July through
  September)", "April charges/arrears"), "from 1 May", relative expressions with units ("a fortnight ago", "two days
  ago", "due settimane fa"), "il 3 del mese scorso", nineteenth-century years with context ("dates to 1887"). Relative
  words become an absolute shifted date only when the document date is known; otherwise they stay relative.
- The shift Δ is never close to a whole number of years, so a day/month without a year never keeps its original form.
- Names: "Dwayne \"Deej\" Hunter" and "Immacolata (Imma) Ruocco" (name, nickname, surname), couples sharing a surname
  ("Kenji and Ruth Nakagawa"), initials before a surname even when it is a word ("G. Rosa, consigliere", "dott. G.
  Righetti"), "known to the staff as", "alias", "chiamata \"Oksi\"", lowercase names after a greeting or a kinship
  word ("ciao marco", "zia carmela") and as chat authors; their lowercase occurrences are replaced and restored.
- Places: Italian streets without "via" after a town or an address cue ("Parma, Bixio 18", "Domicilio fiscale: Madonna
  Pellegrina 40", "dell'Industria 7"), the CAP after them, English streets with "de"/"of"/"y" and "Mall"/"Gate",
  English addresses and UK postcodes inside Italian texts; card numbers with underscores; codes like "PE 2022/0457".
- GLiNER thresholds per label (persons 0.40, places 0.45, organisations and codes 0.55-0.60).
- Optional "leak-proof" mode for medical and legal texts (`fuga_sensibili=True`), off by default (measured cost: +0.2
  points of names, -1.5 points of precision).

### Changed
- Long texts: the round-trip check reads only the blocks the prefilter considers clean; alias alternations are split by
  initial letter; the round-trip diff works line by line. 23,700-character PDF: +435 ms (0.4.0 +1,061 ms, 0.2.0 +743 ms).
  Long sessions with thousands of aliases: about 5 times faster.
- Streaming restore keeps the already emitted text as left context and always holds back a tail as long as the longest
  fake value: identical to the original on 320/320 documents cut at random (0.4.0: 145/320). The visible text arrives
  with a short delay (40-160 characters).
- Fake US/UK towns: when the short list is exhausted, the gazetteer is used (no more repeated aliases in long sessions).

### Measured (final sealed set 4, once, 80 new documents)
- Round trip 80/80, restore after rewrite 99.8%, timeline 88.4%, date leaks 45 (target 0, not met), dates shifted by
  mistake 71, codes 98.6%, names 95.1%, places 84.2% (English 76.9%), precision 91.6%. Real Claude test (9 calls,
  11,775 input and 5,694 output tokens, about 0.60 USD): with the shield 16/16 surnames and 20/20 dates, no invented
  date, no alias left in the summaries.

## [0.4.0] - 2026-10-27

Correctness first: identical round trip guaranteed, one shift for every kind of date, faster first request.

### Added
- Round-trip check on every outgoing text: restore without the model must give the original byte for byte; otherwise
  the piece is sent as a placeholder `⟦Sn⟧` that comes back exactly. Never altered text.
- Dates: partial and relative forms — "ottobre 2026", "07/2025", "Q3 2025", "terzo trimestre", year ranges
  "2019-2021", years with context (built, since, fino al, estate…), ranges "dal 3 al 10 marzo" / "March 3–10, 2025",
  month ranges "marzo-aprile 2025", dates in Italian words, "3 u.s." / "9 corr." / "5 p.v.", "the 14th", "the 3rd of
  last month", "giovedì 8"; the reference month comes from the document date (header or label); law dates (D.Lgs.,
  R.D., Act, Public Law, GDPR "applicabile dal") stay untouched.
- Exact restore of mixed-case surnames ("MACLEOD-Wood" and "MacLeod-Wood"), US state names ("Portland, Oregon"),
  street numbers before the street name, zero padding of dates.
- Italian addresses without "via" in tables ("Bixio 18, interno 4, 43125"), "via dei Mille" / "via dell'Industria",
  CAP after the address or in brackets, more street types (scali, calata, lungarno…); phones "0522 / 296111";
  +44 and +1 numbers inside Italian texts; names: labels mid-line, nicknames ("Gigi (Luigi Valle…)", "il Marchino,"),
  kinship without article ("zia Nella"), attendance lists.
- Common-word lists (Italian ~37,000 forms, English ~10,600) for the prefilter and to reject non-names.
- Sealed final sets: encrypted, hashed, one measurement only.

### Changed
- Long texts are analysed only in the parts the prefilter flags: first request +112 ms (was +286 ms in 0.2.0, +544 ms
  in 0.3.0).
- Corrections by the authors of the first blind set (missing phone numbers, one relative date).

### Measured (final sealed set, once)
- Round trip 80/80, restore after rewrite 99.9%, timeline 89.6%, codes 97.9%, names 95.2%, places 94.0%,
  precision 95.6%. Targets for coverage and timeline not met.

## [0.3.0] - 2026-10-27

English (US and UK), more codes, places and names. The 0.2.0 latency work is now in the main package.

### Added
- Language detection per text (`it`, `en`, `misto`) and US/UK date convention per document; dates keep format,
  language and ordinal suffix ("March 4th", "the 6th day of March"); numeric dates without year ("02/03").
- English detectors and valid surrogates: SSN, ITIN, UK National Insurance number, NHS number (mod 11), ABA routing
  (checksum), sort code, account, passport, driver's licence (incl. UK 16-character), VIN, US/UK plates, US/UK phones
  (fictional ranges), ZIP/ZIP+4, UK postcode, "City, ST", street addresses with the number first.
- English names: titles, roles, labels, "SURNAME, First", attendance lists, sign-offs and greetings, nicknames in quotes or
  brackets, particles (O', Mc, Van der, De La, ap); English alias pools; Italian names in English text keep Italian aliases.
- Italian: cadastral data (foglio, particella, mappale, subalterno, sezione), generic case and ID numbers, CAP after the
  street number, city before "via", frazioni and quartieri, "nato il … a …", kinship cues, "detto/detta", toll-free numbers.
- Dictionaries in `sosia/dizionari` (~6,000 first names, 8,500 surnames, 3,200 Italian comuni, 840 frazioni, 1,900 foreign
  cities, 9,000 US/UK places), used only for recognition.
- Blind benchmark: 80 frozen documents, development/final split, final run locked to once.
- Test with a real model (Claude) on summaries, with and without the shield.

### Changed
- Version 0.2.0 (prefilter, caches, background model, streaming hold-back) merged into the main package.
- No two real values can map to the same fake value of a code type (restore would confuse them).
- Streaming restore also holds back a street number before a street name and phone numbers with brackets.

### Measured (final blind set, once)
- Codes 96.2%, names 97.4%, places 91.8%, precision 90.2%, timeline 91.6%, exact round trip 34/40, restore after rewrite
  100%. Targets (99/98/97/100%) not met.

## [0.2.0] - 2026-10-27

Conversation latency (merged into the main package in 0.3.0).

### Added
- Fast prefilter (< 20 ms): text with nothing potentially personal passes without analysis.
- Per-session memory of results: system prompt, CLI context and already-seen messages are not re-analysed.
- GLiNER "auto" mode: the model runs only on sentences with unknown capitalised words, loaded in
  the background and warmed up; until ready, those words are replaced as a precaution.
- Streaming restore that holds back only the last word when it could become a fake value.

### Changed
- Time to first token through the proxy: from +570–600 ms to +5–9 ms on short messages,
  from +2,417 ms to +26 ms on a ~2,500-character document (CPU, fake provider).
- Blind-set recall unchanged (names 94.3%, places 95.7%, codes 75.4%).

## [0.1.0] - 2026-10-27

First working version.

### Added
- Realistic, consistent surrogates: valid codice fiscale rebuilt from fake name, shifted birth date
  and fake birthplace; valid IBAN (CIN + mod 97) and partita IVA; constant aliases for name variants.
- Session-wide date shift by whole weeks (timeline and weekdays preserved); legal references untouched.
- Local age/deadline computation with `⟦OGGI⟧`, `⟦ETA:…⟧`, `⟦GIORNI:…⟧`, `⟦SCADENZA:…⟧` markers,
  so today's date is not disclosed to the provider.
- Restore, including streaming, rewritten aliases, initials and recomputed dates; uncertain spots reported.
- Anthropic (`/v1/messages`) and OpenAI (`/v1/chat/completions`, `/v1/responses`) compatible local proxy.
- Formats: TXT, MD, CSV, JSON, DOCX, XLSX, PDF (text only), EML.
- Encrypted local map (AES-256-GCM, DPAPI or scrypt) with authenticated expiry.
- Optional local NER with GLiNER (CPU only, offline).
- Benchmark with invented documents and three blind sets.
