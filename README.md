# ProofLedger AI

> Object-centric, uncertainty-aware financial close controller for Razorpay merchants.

ProofLedger reconstructs how merchant orders become captured payments, refunds, settlements,
bank credits, and accounting entries. It combines deterministic financial controls with bounded
AI assistance, minimum-evidence human review, and independently verifiable close certificates.

## Why it exists

Finance teams do not only need records that appear similar. They must prove that the settlement
equation balances, that money followed an allowed lifecycle, that every journal has evidence, and
that unresolved material differences block the close.

## Core guarantees

- Money is stored and calculated as integer paise.
- Source records are immutable and hashed.
- AI can explain and rank evidence but cannot approve financial truth.
- Semantic matches require human review.
- Every journal proposal balances before it can be reviewed.
- Every closed settlement emits a machine-verifiable certificate.
- The deterministic pipeline remains available without Gemini.

## Real versus simulated

This Buildathon project uses deterministic, synthetic datasets shaped after public Razorpay API
entities. It does not move real money, execute refunds, post into an accounting system, or process
real customer information. The optional Razorpay connector contract is intentionally disabled until
test credentials are available.

## Planned demo

1. Load five synthetic finance sources containing more than 1,000 records.
2. Build an object-centric lifecycle graph.
3. Reconcile exact and composite settlement evidence.
4. Detect financial and process-control violations.
5. Abstain when an ambiguous bank credit has multiple plausible settlements.
6. Ask one high-value evidence question and propagate the answer.
7. Generate a balanced journal proposal and settlement proof certificate.
8. Change one source amount by one rupee and watch independent verification fail.
9. Compare exact, fuzzy, and ProofLedger benchmarks on held-out labels.

## Local development

Backend setup and frontend setup instructions will be finalized with their respective milestones.
Copy `.env.example` to `.env` locally; never commit secrets.

## Author

PARIDHIPAWAIYA

