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

## 2:15–3:05 — Safe abstention and human review

Open **Evidence review**.

Show ranked candidates, amount/date evidence, expected information gain, and the requested UTR.

Key sentence: “When evidence is ambiguous, the product does not hallucinate certainty. It asks
for the smallest missing proof.”

## 3:05–4:10 — Balanced journal and proof certificate

Return to settlement 0000.

- Show debit/credit equality.
- Explain that the journal is proposed, never posted.
- Issue the certificate.
- Verify it successfully.

Then click **Change ₹1**. Verification must fail on evidence_hashes_match.

Key sentence: “The certificate carries the claim and the evidence hashes needed to challenge it.”

## 4:10–5:05 — Honest benchmark

Open **Safety benchmark**.

Explain:

- exact matching is precise but misses missing references;
- fuzzy matching boosts recall but silently auto-approves wrong rows;
- ProofLedger sends uncertainty to review and has zero wrong auto-approvals in this scenario.

State clearly that results are synthetic.

## 5:05–6:00 — AI boundary and job signal

“AI only explains deterministic exceptions and phrases evidence questions. It cannot approve
matches, journals, or financial close. The repository includes domain invariants, 18 backend/API
tests, frontend lint/tests/build, CI, a production dependency audit, Docker deployment, and honest
limitations.”

Finish on the dashboard with: “ProofLedger is not another finance chatbot. It is an evidence and
control system with AI at the language boundary.”

## Backup if Gemini is unavailable

Do not delay the demo. The deterministic fallback produces explanations and the complete control,
review, graph, benchmark, journal, and certificate workflow remains functional.
