# Threat Model

## Protected assets

- source financial evidence and its lineage;
- reconciliation decisions and controller actions;
- journal proposals;
- settlement certificates;
- Gemini API key and connector credentials.

## Trust boundaries

1. Source system to normalization layer.
2. Normalized evidence to finance-control engine.
3. Server API to browser UI.
4. Deterministic control result to optional Gemini service.
5. Proposed journal/certificate to human controller.

## Threats and mitigations

| Threat | Current mitigation | Production requirement |
| --- | --- | --- |
| Source record changed after ingestion | Frozen model, canonical SHA-256, record-hash manifest, Ed25519 verification | Append-only object storage and KMS/HSM-backed tenant signing key |
| Source file replaced or mapping rewritten | Manifest binds file SHA-256, mapping, public key, timestamp, and record hashes | Retain encrypted original with tenant/period metadata and key rotation |
| Partial import leaves an inconsistent ledger | All rows validate before any record or manifest is committed | Durable database transaction and idempotency key |
| Signed data becomes authoritative without approval | Commit and activation are separate; activation re-verifies and records actor/rationale in a hashed event | Authenticated maker-checker policy and scoped roles |
| Second bank row hides a known mismatch | Activation rejects bank evidence when a row already exists for the settlement/reference | Source correction and governed exception workflow |
| Activation removal silently changes prior conclusions | Deactivation is hashed, recomputes the close, and causes dependent certificate verification to fail | Certificate revocation registry and period locking |
| LLM invents evidence | Only deterministic control JSON enters prompt; output advisory | Prompt/eval monitoring and data-loss prevention |
| LLM sees transaction PII during schema mapping | Only header names/targets are sent; output allow-listed; human confirmation required | DLP-classified headers, provider agreement, or local mapping model |
| Prompt injection in a malicious column header | Model cannot emit new fields/columns or commit; confirmation resets after suggestion | Header sanitization, model isolation, prompt-injection evaluation |
| Semantic match silently approved | Domain invariant rejects semantic auto-approval | Maker-checker workflow and authorization policy |
| Controller fabricates or rewrites review evidence | Original row stays immutable; action and attachment are separately hashed; all controls rerun | Signed file storage, authenticated actor, maker-checker approval, revocation |
| Duplicate evidence masks an amount mismatch | API rejects new-row attachment when an exact linked bank row already exists | Source-system correction workflow and exception approval policy |
| Duplicate journal | Deterministic posting signature control | Idempotency key against accounting connector |
| Certificate replay | Certificate binds settlement ID, issue time, evidence hashes | Tenant ID, period ID, signature, expiry/revocation |
| Cross-tenant evidence access | Not applicable in single-tenant demo | Row-level security and tenant-scoped keys |
| API key exposed to frontend | Gemini runs server-side only | Secret manager and rotation |
| Malicious CSV formula/content | Extension/size/encoding/shape bounds; React escapes samples; manifests contain no row values | MIME sniffing, malware scan, quarantine, neutralized CSV re-export |
| Memory exhaustion through uploads | API reads at most 5 MB + 1 byte; row/column/cell caps | Streaming parser, request-body proxy limit, per-tenant quotas |
| Amount precision loss | Integer paise throughout | Currency-specific minor-unit registry |
| Unauthorized journal posting | Demo cannot post; proposal stays review-required | OAuth scopes, maker-checker approval, audit log |

## Known demo limitations

Import manifests use a real Ed25519 signature, but the private key is ephemeral and the public key
is self-contained; without an externally pinned fingerprint it proves integrity, not organizational
identity. Close certificates, controller resolutions, and activation actions are hashed but are not
externally signed. CSV staging, manifests, and activation history are in memory. Activated evidence
does participate in the close, but the supplied actor identity is not authenticated. The demo has
no tenant isolation. These are explicit non-production boundaries, not hidden claims.
