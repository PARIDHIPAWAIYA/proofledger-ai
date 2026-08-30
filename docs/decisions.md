# Architecture Decision Records

## ADR-001: Integer paise for money

All financial values are represented as integers in the smallest currency unit. Floating-point
arithmetic is prohibited in authoritative calculations.

## ADR-002: Deterministic authority before AI

Exact identifiers, component equations, financial controls, journal balancing, and certificate
verification are deterministic. Gemini is advisory and evidence-bound.

## ADR-003: Object-centric close model

Orders, payments, refunds, settlements, bank credits, and journals are modeled as related objects
and events instead of forcing all activity into one table or case identifier.

## ADR-004: Synthetic official-schema fixtures

The submission uses synthetic records inspired by public Razorpay entity shapes because no test
credentials are available. The product must not imply that simulated records came from Razorpay.

## ADR-005: Append-only review evidence

Controller actions never mutate the normalized source record. A separately hashed resolution
creates a derived evidence overlay, after which reconciliation, controls, graph construction, and
certificate eligibility are recomputed. Review authority can add evidence but cannot bypass a
failed accounting equation.

## ADR-006: Atomic, signed CSV ingestion

Uploads are untrusted and staged before authority enters the evidence layer. File shape, mapping,
amount unit, and every row are validated before an all-or-nothing commit. The resulting manifest
binds the source-file SHA-256, controller-confirmed mapping, canonical record hashes, timestamp,
and signing public key; an Ed25519 signature makes post-import mutation detectable. The demo uses
an ephemeral key, while production requires a KMS/HSM-backed trust anchor.

## ADR-007: Header-only AI schema assistance

Schema ambiguity benefits from language understanding, but finance rows may contain sensitive
data and AI cannot be authoritative. Gemini receives column names and allowed targets only. Its
response is constrained to those values, cannot invoke commit, and resets controller confirmation.
Deterministic aliases remain the offline fallback.

## ADR-008: Signed does not mean authoritative

Cryptographic integrity and controller authority are different claims. Committing a CSV creates a
signed, inactive evidence batch. A separate activation verifies the signature and record hashes,
checks source-identity collisions and anti-masking rules, captures actor/rationale in an append-only
hashed event, and recomputes all downstream outputs. Deactivation is equally explicit and auditable.
Production must add authenticated maker-checker authorization and transactional period state.

## ADR-009: Event-replayed import authority

Committed manifests and their normalized records are persisted transactionally through SQLAlchemy.
Activation state is not stored as a mutable boolean; it is reconstructed by replaying append-only
activation/deactivation events in database sequence order. Startup refuses persisted objects whose
model validation, record hashes, Ed25519 signature, hash set, or activation audit hash fails.
SQLite keeps local setup frictionless while psycopg supports managed PostgreSQL in deployment.
