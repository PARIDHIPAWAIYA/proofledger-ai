# Architecture

ProofLedger separates deterministic financial authority from probabilistic assistance.

## System flow

~~~text
merchant orders ─┐
payment recon ────┤
refund register ──┼─> bounded staging + confirmed schema mapping
bank statement ───┤             │
general ledger ───┘             ▼
                    atomic normalization + signed manifest
                                │
                                ▼
                         evidence hashing
                                │
                                ▼
                         object/event graph
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
           reconciliation   finance controls   lineage paths
                 │              │              │
                 └──── uncertainty boundary ───┘
                                │
                     minimum-evidence review
                                │
                    balanced journal proposal
                                │
                 settlement close certificate
~~~

## Evidence model

Each normalized record carries:

- a stable internal record ID and source-system identifier;
- a business object type and external identifier;
- integer-paise amount, currency, timestamp, and status;
- optional order, payment, refund, settlement, and bank references;
- source-specific attributes;
- SHA-256 over its canonical JSON payload.

Pydantic freezes records after validation. Certificate verification recalculates the source hash
instead of trusting the stored value.

## Ingestion boundary

All five source systems can be imported: merchant orders, Razorpay settlements, the refund
register, bank statements, and the general ledger. Each has its own canonical schema, alias set,
and required fields, so a ledger export cannot be committed as a bank statement.

Imports are deliberately one source per manifest. Each file therefore carries its own signature,
its own controller approval, and its own reversal, and the audit trail records which specific
source a controller admitted. Activating any single source re-runs reconciliation and all ten
controls across every active source together.

The intake service accepts UTF-8 CSV/TSV/text exports up to 5 MB, 10,000 rows, 60 columns, and
5,000 characters per cell. It rejects NUL bytes, duplicate/empty headers, ragged rows, invalid
dates, negative amounts, reused mappings, and incomplete required schemas. Preview is a staging
operation only. Commit validates every row before storing any record, so a single invalid row
rejects the entire batch.

Deterministic aliases/fuzzy header scores produce the first mapping. Optional Gemini receives only
the source column names, target field names, and deterministic proposal. Its response is allow-list
validated and remains unconfirmed; the controller must review the mapping and amount unit.

Every commit creates an Ed25519-signed manifest containing the original file SHA-256, confirmed
mapping, normalized record hashes, import timestamp, and public key. Verification recomputes the
manifest hash, signature, and every record hash. The demo key is generated at process start; a
production verifier must pin a tenant key or trust a KMS-backed certificate chain.

Signing and authority are separate operations. A signed batch remains staged until a controller
supplies an identity and rationale. Activation re-verifies the complete manifest, rejects record
identity collisions and duplicate bank rows that could mask an existing mismatch, then adds the
records to the authoritative evidence view. Graphs, reconciliation, controls, reviews, journal
proposals, and certificates are derived again. Activation/deactivation events are append-only and
carry their own canonical SHA-256 audit hash.

## Persistence boundary

SQLAlchemy stores committed manifests, normalized record payloads, and ordered activation events
in one database. Import commit writes the manifest and all records in a single transaction.
Activation events are append-only; active state is reconstructed by replaying them in database
sequence order. On process startup, ProofLedger validates every stored Pydantic model, evidence
hash, manifest hash, Ed25519 signature, record-hash set, and activation hash before hydrating the
authoritative view. SQLite is the zero-configuration default; the same tables run on PostgreSQL
through psycopg.

## Object-centric graph

The graph is bipartite at its evidence layer:

- event nodes represent immutable source observations;
- object nodes represent orders, payments, refunds, settlements, bank credits, and journals;
- event-to-object edges show which observation touched which object;
- object-to-object edges show paid-by, refunded-by, settled-in, credited-as, and posted-as
  lifecycle relationships.

This avoids forcing a refund, settlement, and ledger line into one artificial case ID.

## Reconciliation hierarchy

1. **Exact:** business ID or bank reference plus amount.
2. **Composite:** exact amount, acceptable date window, and a unique candidate.
3. **Semantic:** narration or imperfect numeric evidence; always human-reviewed.
4. **Abstained:** absent, low-confidence, or near-tied candidates.

An invariant in the domain model rejects any semantic decision marked auto-approved.

The live abstention boundary is deterministic: a fixed safe-confidence floor plus a
near-tie margin between the top two candidates. It does not consult the calibrator, because a
runtime match must not depend on labelled data.

Calibration is a separate, explicitly labelled evaluation surface. `GET /api/v1/calibration`
splits the labelled payouts, fits a split-conformal minimum-confidence threshold on one half,
measures coverage on the unseen half, and reports the candidate-set size that threshold would
produce for each open review question. It reports on the abstention boundary; it does not
override it.

## AI boundary

The optional Gemini adapters receive either a serialized deterministic control result or a list of
column names—never uploaded row values. Prompts forbid inventing records or approving a close, and
outputs are parsed into strict response schemas plus allow-list validation. Failure or absence of
Gemini returns deterministic behavior. Gemini never runs inside:

- money calculations;
- control pass/fail logic;
- journal balancing;
- evidence hashing;
- certificate issuance or verification.

## Controller evidence overlays

Review resolution is append-only. The controller submits a bank UTR, statement-row facts, an
attachment SHA-256, actor, and rationale. ProofLedger stores a separately hashed resolution and
builds a derived evidence view for reconciliation and controls. The original normalized record and
its source hash remain unchanged.

The derived view is never trusted merely because a human submitted it. Every reconciliation and
finance control reruns. A missing bank row can become close-ready when the supplied amount and UTR
pass; an existing ₹1 mismatch remains blocked, and the API rejects a duplicate row intended to hide
that source discrepancy.

## Runtime

The Buildathon demo regenerates the same deterministic base workspace so cloning the repository
produces the scenario without credentials. Signed imports and activation events are database-backed;
temporary CSV previews, review resolutions, and certificates remain in memory. Production would
add authenticated connectors, encrypted tenant storage, durable review/certificate repositories,
period locking, and maker-checker authorization.

## Frontend

The React console consumes typed API contracts. Chart and graph views are lazy-loaded. The UI
does not compute authoritative finance results; it displays server-side decisions and invokes
server-side import, manifest, and certificate operations.
