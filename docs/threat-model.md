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
| Source record changed after ingestion | Frozen model and SHA-256 canonical hash | Append-only object storage and signed ingestion manifest |
| LLM invents evidence | Only deterministic control JSON enters prompt; output advisory | Prompt/eval monitoring and data-loss prevention |
| Semantic match silently approved | Domain invariant rejects semantic auto-approval | Maker-checker workflow and authorization policy |
| Duplicate journal | Deterministic posting signature control | Idempotency key against accounting connector |
| Certificate replay | Certificate binds settlement ID, issue time, evidence hashes | Tenant ID, period ID, signature, expiry/revocation |
| Cross-tenant evidence access | Not applicable in single-tenant demo | Row-level security and tenant-scoped keys |
| API key exposed to frontend | Gemini runs server-side only | Secret manager and rotation |
| Malicious CSV formula/content | Demo generator only | MIME/size validation, neutralized exports, sandboxed parsing |
| Amount precision loss | Integer paise throughout | Currency-specific minor-unit registry |
| Unauthorized journal posting | Demo cannot post; proposal stays review-required | OAuth scopes, maker-checker approval, audit log |

## Known demo limitations

The certificate is hashed, not cryptographically signed by an external key. The in-memory workspace
has no authentication or tenant isolation. These are explicit non-production boundaries, not hidden
claims.
