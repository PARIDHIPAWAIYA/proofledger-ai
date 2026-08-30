# Architecture

ProofLedger separates deterministic financial authority from probabilistic assistance.

## System flow

~~~text
merchant orders ─┐
payment recon ────┤
refund register ──┼─> normalization + evidence hashing
bank statement ───┤             │
general ledger ───┘             ▼
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

## AI boundary

The optional Gemini adapter receives a serialized deterministic control result. Its prompt forbids
inventing records or approving a close, and its output is parsed into a strict response schema.
Failure or absence of Gemini returns a deterministic explanation. Gemini never runs inside:

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

The Buildathon demo uses an in-memory deterministic workspace so cloning the repository produces
the same scenario without credentials. The domain layer is storage-agnostic; production would
replace the workspace with durable repositories and authenticated connectors.

## Frontend

The React console consumes typed API contracts. Chart and graph views are lazy-loaded. The UI
does not compute authoritative finance results; it displays server-side decisions and invokes
server-side certificate operations.
