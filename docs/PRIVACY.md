# BeeOrganizer 2.0: privacy and data flows

This page describes what BeeOrganizer 2.0 does with your files. It supports the GDPR documentation
required by the V2 specification (§10.7, §12.3 item 7). **It is not a certificate of GDPR compliance**: roles,
legal bases, the provider agreement and the risk analysis depend on how and where it is deployed.

## Default: everything stays on the computer

BeeOrganizer watches Downloads, reads each new file **locally**, names it, compares it with your approved
projects and keeps a local history for Undo. None of this needs Internet or an API key (PR-01, PR-21).

**Cloud analysis is off** when the app is first started (PR-02). It can be turned on only from
**🐝 → Privacy and cloud analysis…**, after reading the information shown there.

## Local check before any network call (PR-17)

| Step | What happens |
|---|---|
| 1. Download finished | Size stable (6 s), file no longer in use, local tracking id |
| 2. Local inspection | Text read on the computer; class **P0 / P1 / P2 / INCONNU**, no network |
| 3. Policy | P1, P2, INCONNU or project "always local": no call, local name |
| 4. Switch | P0 but cloud off: local name |
| 5. Minimisation | Redacted excerpt; if anything risky remains or too little is left: local name |
| 6. Optional call | Only the validated excerpt is sent, with a one-time permit for this file |
| 7. Filing | Project rules (§4); never re-checks cloud permission from the destination |

| Class | Examples | Cloud |
|---|---|---|
| P0 public / low risk | brochure, public documentation, press release | Possible only if switched on, after minimisation |
| P1 confidential / personal | invoice, contract, quote, CV, HR, e-mail / phone / IBAN / address | Blocked |
| P2 very sensitive | passport, ID card, residence permit, asylum, health, criminal record, national number, professional secrecy | Blocked, no bypass |
| INCONNU | unreadable or scanned PDF, image, video, archive, encrypted, detector error | Blocked |

## What can be sent, and to whom

* **Provider:** OpenAI API (Chat Completions), model chosen in Privacy (default `gpt-5-mini`). Processing may
  take place outside the EEA (GDPR chapter V).
* **Data:** for one P0 document, a redacted excerpt (max. 1,200 characters, with e-mails, URLs, paths, IBANs,
  phone numbers, long numbers and identifiers removed) and the file extension.
* **Never sent:** the file, its name, its folder path, images, video frames, EXIF / GPS, metadata, documents
  of other classes, files of "always local" projects.
* **Retention at the provider:** the request asks for `store=false`. OpenAI may still keep API data up to
  30 days for abuse monitoring, with exceptions. Check the current terms and the Data Processing Addendum for
  the endpoint used: https://developers.openai.com/api/docs/guides/your-data and
  https://openai.com/policies/data-processing-addendum/
* **Answer:** treated as untrusted data: strict JSON schema, length and characters checked, no URL, and the
  title must use words of the excerpt (otherwise the local name is kept).

Turning the switch off stops every new request immediately, including ones being prepared (PR-22).
Turning it on is the user's choice for their files; it is **not** the GDPR consent of people named in the
documents (PR-31).

## What is stored on the computer

`beeorganizer_v2.sqlite3` in the app data folder (`%APPDATA%\SmartFileOrganizer` on Windows,
`~/Library/Application Support/SmartFileOrganizer` on macOS):

* approved projects (name, aliases, references, exclusions, path, "always local");
* for each processed file: technical id, content hash, original and current name / path, state,
  sensitivity class and generic reason codes (e.g. `IBAN`, `PASSPORT`);
* decisions (candidate projects, scores, evidence codes), operations for Undo, proposals;
* privacy events (class, action, rule, time).

**Never stored:** extracted text, excerpts, API payloads, API keys (PR-24, PR-25).
The API key is kept in the system vault (macOS Keychain / Windows Credential Manager) (PR-23).

**Retention (PR-26):** technical events and decisions 30 days, Undo history 90 days, then purged
automatically at start-up. **Purge history now** in Privacy deletes them at once (projects and files stay).

## Roles (to be confirmed per deployment, PR-30)

* The organisation using BeeOrganizer on its computers is normally the **controller** of the processing of
  its documents.
* BeeOrganizer runs locally; the publisher receives no document data.
* When cloud analysis is on, OpenAI acts as a **processor** (or sub-processor) for the excerpts it receives.

## Before distributing beyond the team (AC-14)

* Privacy notice for users (purposes, data, provider, countries, retention, rights, contact).
* OpenAI DPA and transfer mechanism checked for the account used.
* Record of processing and risk analysis; DPIA assessed for the context (not presumed mandatory).
* Incident and data-subject request procedure.
