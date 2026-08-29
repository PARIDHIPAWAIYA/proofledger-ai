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

