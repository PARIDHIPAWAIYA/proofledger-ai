# Evaluation Protocol

## Question

Can ProofLedger recover correct settlement-to-bank links while avoiding silent automatic errors?

## Data

The benchmark uses the deterministic synthetic generator with hidden settlement-to-bank ground
truth. Matching methods receive the same evidence records, not the label map.

## Compared methods

- **Exact ID:** requires matching bank reference and amount.
- **Fuzzy narration:** selects the bank row with the strongest narration similarity, then amount.
- **ProofLedger:** exact → composite → semantic/review with safe abstention.

## Metrics

- Precision: correct predicted links / all predicted links.
- Recall: correct predicted links / all true links.
- F1: harmonic mean of precision and recall.
- Human review rate: settlements not automatically cleared.
- Incorrect automatic approvals: predicted auto-approved links absent from ground truth.

The last metric matters most financially: a tool can produce high recall by matching everything.

## Included results

Two configurations are reported because they answer different questions. Always state which one
a number came from.

**Default workspace** — `seed 2026`, 600 orders, 12 settlement batches. This is what the running
API, the operator console, and the deployed demo return.

| Method | Precision | Recall | F1 | Review | Wrong auto |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact ID | 1.000 | 0.727 | 0.842 | 0.000 | 0 |
| Fuzzy narration | 0.750 | 0.818 | 0.783 | 0.000 | 3 |
| ProofLedger | 1.000 | 1.000 | 1.000 | 0.167 | 0 |

**Small CLI configuration** — `--seed 11 --orders 120 --settlement-size 20`, 6 settlement batches.
A higher proportion of its payouts carry an injected anomaly, so the baselines degrade further.
The test suite pins this configuration.

| Method | Precision | Recall | F1 | Review | Wrong auto |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact ID | 1.000 | 0.400 | 0.571 | 0.000 | 0 |
| Fuzzy narration | 0.500 | 0.600 | 0.546 | 0.000 | 3 |
| ProofLedger | 1.000 | 1.000 | 1.000 | 0.333 | 0 |

Precision, recall, and review rate move with the anomaly density. The safety result does not:
fuzzy matching silently auto-approves three incorrect links in both, and ProofLedger auto-approves
zero incorrect links in both.

## Calibration

`GET /api/v1/calibration` runs a real split-conformal procedure over the labelled
settlement-to-bank confidences:

1. Score every labelled payout by the confidence the engine assigned to its *true* bank link.
2. Split those scores in half deterministically.
3. Fit the minimum-confidence threshold on the first half at the requested error level (alpha).
4. Report empirical coverage on the second half, which the fit never saw.
5. Apply the threshold to the live review queue and report each open question's candidate-set size.

The response exposes calibration sample size, alpha, minimum confidence, calibration coverage,
held-out coverage, singleton and empty set counts, and the exchangeability and
candidate-generation assumptions.

An empty candidate set means no bank evidence cleared the threshold — the correct outcome when a
payout genuinely has no bank credit. A singleton set means one candidate survived and may be
recommended for review. A calibrated set never auto-approves; it only sizes the question.

This is a dataset-level coverage tool, not a claim that a particular transaction is certainly
correct. With 11 labelled payouts the calibration split is small, and the reported coverage should
be read as a demonstration of the procedure rather than a tight statistical guarantee.

## Caveats

- Synthetic performance is not production merchant performance.
- The included sample is intentionally small at settlement level.
- Real evaluation needs temporal splits across merchants, banks, payment methods, and outage days.
- A merchant-specific materiality policy may change the review threshold.
- Fuzzy baseline design is intentionally simple and fully inspectable.

## Reproduce

~~~powershell
proofledger --seed 11 --orders 120 --settlement-size 20 benchmark
~~~
