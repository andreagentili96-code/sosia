# Security policy / Sicurezza

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private
vulnerability reporting ("Security" tab → "Report a vulnerability") on this repository.
We aim to acknowledge reports within 7 days.

Especially relevant:

- personal data that leaks to the cloud provider (a value that is detected but still sent in clear);
- ways to recover real values from the pseudonymised text (e.g. deriving the date shift Δ);
- access to the local encrypted map (DPAPI / scrypt vault) by another user or process;
- the local proxy being reachable from web pages (Origin / Host checks, DNS rebinding) or other machines.

Please **never include real personal data** in a report: use invented examples.

## Threat model in short

Sosia reduces what a cloud LLM provider sees; it is **not** a guarantee of anonymisation.
Detection recall on unseen documents is below 100% (see `docs/LIMITATIONS.md` and the benchmark table in
the README). Context, rare events and the structure of a document can still identify a person.
The real↔fake map stays on the local machine, encrypted (AES-256-GCM, key protected with Windows
DPAPI or derived with scrypt from `SOSIA_PAROLA`) and with an authenticated expiry.

## Segnalare una vulnerabilità (italiano)

Non aprire una issue pubblica: usa la segnalazione privata di GitHub (scheda «Security»).
Non inserire mai dati personali veri nelle segnalazioni. I limiti noti sono in `docs/LIMITI.md`.
