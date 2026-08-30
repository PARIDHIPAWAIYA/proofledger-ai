# Six-Minute Judge Demo

## 0:00–0:35 — Problem and promise

“Reconciliation tools usually answer: which rows look similar? A finance controller must answer:
can I prove this settlement, and what exactly blocks the close? ProofLedger reconstructs the
money lifecycle, abstains when evidence is unsafe, and emits a verifiable close certificate.”

Show **Close command** and point to records, critical exceptions, and safe automation.

## 0:35–1:20 — One graph across five systems

Open **Lifecycle graph** on settlement 0000.

Explain event nodes versus business objects and trace:

order → captured payment → settlement → bank credit → journal.

Key sentence: “A refund and a payout do not fit one spreadsheet case ID, so the graph preserves
their real many-to-many lifecycle.”

## 1:20–2:15 — Deterministic controls

Open **Settlements**, choose settlement 0002, and show:

- settlement components;
- linked bank record;
- CTRL-05 difference;
- blocked close state.

Key sentence: “Gemini did not decide this. Integer-paise accounting did.”

Try issuing a certificate. The API returns a conflict naming the blocking control.

## 2:15–3:25 — Safe abstention and evidence-bound review

Open **Evidence review**.

Open the missing-bank question. Show the low-confidence candidate, then keep **Attach new statement
row** selected. Submit the verified UTR.

Point out the signed-looking audit fingerprint, queue reduction, and settlement transition from
blocked to ready. Explain that the original source data was not rewritten; reconciliation and all
controls reran over an evidence overlay.

Then show settlement 0002's locked review card: an exact row exists with a ₹1 difference, so the
API refuses a duplicate evidence row and requires source correction.

Key sentence: “A human can add a missing fact, but cannot vote a broken equation into passing.”

## 3:25–4:20 — Balanced journal and proof certificate

Return to settlement 0000.

- Show debit/credit equality.
- Explain that the journal is proposed, never posted.
- Issue the certificate.
- Verify it successfully.

Then click **Change ₹1**. Verification must fail on evidence_hashes_match.

Key sentence: “The certificate carries the claim and the evidence hashes needed to challenge it.”

## 4:20–5:10 — Honest benchmark

Open **Safety benchmark**.

Explain:

- exact matching is precise but misses missing references;
- fuzzy matching boosts recall but silently auto-approves wrong rows;
- ProofLedger sends uncertainty to review and has zero wrong auto-approvals in this scenario.

State clearly that results are synthetic.

## 5:10–6:00 — AI boundary and job signal

“AI only explains deterministic exceptions and phrases evidence questions. It cannot approve
matches, journals, or financial close. The repository includes domain invariants, 23 backend/API
tests, frontend lint/tests/build, CI, a production dependency audit, Docker deployment, and honest
limitations.”

Finish on the dashboard with: “ProofLedger is not another finance chatbot. It is an evidence and
control system with AI at the language boundary.”

## Backup if Gemini is unavailable

Do not delay the demo. The deterministic fallback produces explanations and the complete control,
review, graph, benchmark, journal, and certificate workflow remains functional.
