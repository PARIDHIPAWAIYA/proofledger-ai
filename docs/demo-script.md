# Six-Minute Judge Demo

## 0:00–0:35 — Problem and promise

“Reconciliation tools usually answer: which rows look similar? A finance controller must answer:
can I prove this settlement, and what exactly blocks the close? ProofLedger reconstructs the
money lifecycle, abstains when evidence is unsafe, and emits a verifiable close certificate.”

Show **Close command** and point to records, critical exceptions, and safe automation.

## 0:35–1:30 — Real file to signed evidence

Open **Evidence intake** and click **Run judge-ready demo file**.

- Point out the original file SHA-256 and read-only sample.
- Show deterministic mapping confidence and click **Improve with bounded AI**.
- Stress that only headers go to Gemini and controller confirmation resets.
- Confirm the mapping, sign the import, verify it, then simulate a ₹1 mutation.
- Verify again, enter controller authority, and activate the signed source.
- Show the review queue fall and the settlement move from blocked to ready, then open the dashboard
  and point to the active-import provenance banner.

Key sentence: “AI understands the shape, deterministic code validates the money, cryptography
protects the batch, and a separately audited controller action decides whether it enters the close.”

## 1:30–2:10 — One graph across five systems

Open **Lifecycle graph** on settlement 0000. The default **Lifecycle spine** reads left to right:

50 merchant orders → 50 captured payments → 3 refunds → settlement → bank credit → journal.

Point at the folded counts, then switch to **Every record** to show the same component with all
206 member records and source events expanded.

Key sentence: “A refund and a payout do not fit one spreadsheet case ID, so the graph preserves
their real many-to-many lifecycle — folded for reading, expandable for proof.”

## 2:10–2:50 — Deterministic controls

Open **Settlements**, choose settlement 0002, and show:

- settlement components;
- linked bank record;
- CTRL-05 difference;
- blocked close state.

Key sentence: “Gemini did not decide this. Integer-paise accounting did.”

Try issuing a certificate. The API returns a conflict naming the blocking control.

## 2:50–3:55 — Safe abstention and evidence-bound review

Open **Evidence review**.

Open the missing-bank question. Show the low-confidence candidate, then keep **Attach new statement
row** selected. Submit the verified UTR.

Point out the signed-looking audit fingerprint, queue reduction, and settlement transition from
blocked to ready. Explain that the original source data was not rewritten; reconciliation and all
controls reran over an evidence overlay.

Then show settlement 0002's locked review card: an exact row exists with a ₹1 difference, so the
API refuses a duplicate evidence row and requires source correction.

Key sentence: “A human can add a missing fact, but cannot vote a broken equation into passing.”

## 3:55–4:40 — Balanced journal and proof certificate

Return to settlement 0000.

- Show debit/credit equality.
- Explain that the journal is proposed, never posted.
- Issue the certificate.
- Verify it successfully.

Then click **Change ₹1**. Verification must fail on evidence_hashes_match.

Key sentence: “The certificate carries the claim and the evidence hashes needed to challenge it.”

## 4:40–5:25 — Honest benchmark

Open **Safety benchmark**.

Explain:

- exact matching is precise but misses missing references;
- fuzzy matching boosts recall but silently auto-approves wrong rows;
- ProofLedger sends uncertainty to review and has zero wrong auto-approvals in this scenario.

Scroll to **split-conformal calibration** and say: “The abstention threshold is not a number I
picked. It is fitted on half the labelled payouts and measured on the half the fit never saw.”

State clearly that results are synthetic, and name which configuration the numbers came from.

## 5:25–6:00 — AI boundary and job signal

“AI only explains deterministic exceptions and suggests mappings from header names. It cannot see
transaction rows or approve imports, matches, journals, or financial close. The repository includes
domain invariants, 39 backend/API tests, frontend lint/tests/build, restart-persistence tests, CI, a production dependency
audit, Docker deployment, and honest limitations.”

Finish on the dashboard with: “ProofLedger is not another finance chatbot. It is an evidence and
control system with AI at the language boundary.”

## Backup if Gemini is unavailable

Do not delay the demo. The deterministic fallback produces explanations and the complete control,
review, graph, benchmark, journal, and certificate workflow remains functional.
