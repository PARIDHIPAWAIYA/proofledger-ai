# Deterministic Control Catalog

All controls run without an LLM.

| ID | Assertion | Failure severity | Close impact |
| --- | --- | --- | --- |
| CTRL-01 | Canonical payload reproduces every stored evidence hash | Critical | Block affected evidence |
| CTRL-02 | Merchant order has an equal captured payment | Critical | Block order lifecycle |
| CTRL-03 | Gross − refunds − fees − tax = settlement net | Critical | Block settlement |
| CTRL-04 | Processed settlement has linked bank evidence | Critical | Block settlement |
| CTRL-05 | Linked bank credit equals settlement net | Critical | Block settlement |
| CTRL-06 | No duplicate ledger posting signature | Critical | Block affected posting |
| CTRL-07 | Exactly one ledger posting equals settlement net | Critical | Block settlement |
| CTRL-08 | Member payments precede settlement processing | Critical | Block settlement |
| CTRL-09 | All evidence uses the expected currency partition | Critical | Block mixed-currency close |
| CTRL-10 | Refund references resolve to known order and payment | Warning | Review affected refund |

## Control result contract

Every result includes control ID, status, severity, affected object IDs, evidence record IDs,
expected and observed paise where relevant, plain-language explanation, and remediation.

The UI can ask Gemini to rewrite an already-determined result, but Gemini cannot alter these fields.

## Seeded failures

The default synthetic scenario includes:

- one missing bank credit;
- one bank credit larger than the settlement by exactly ₹1;
- bank rows with missing settlement/UTR references;
- one duplicate ledger posting.

The generator stores ground truth separately from matching inputs.
