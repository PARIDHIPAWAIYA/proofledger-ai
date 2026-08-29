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

## Included result

| Method | Precision | Recall | F1 | Review | Wrong auto |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact ID | 1.000 | 0.400 | 0.571 | 0.000 | 0 |
| Fuzzy narration | 0.500 | 0.600 | 0.546 | 0.000 | 3 |
| ProofLedger | 1.000 | 1.000 | 1.000 | 0.333 | 0 |

## Calibration

The split-conformal helper converts held-out true-match confidence scores into a minimum candidate
threshold for a requested error level. It exposes:

- calibration sample size;
- alpha;
- minimum confidence;
- empirical calibration coverage;
- exchangeability and candidate-generation assumptions.

This is a dataset-level coverage tool, not a claim that a particular transaction is certainly
correct.

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
