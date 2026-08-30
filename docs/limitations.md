# Limitations

- Synthetic data cannot reproduce every production settlement behavior.
- Candidate-set coverage depends on the calibration and evaluation distributions.
- Proposed journals require professional accounting review before any production use.
- The prototype does not implement authentication or multi-tenant isolation.
- The review demo hashes a synthetic statement payload; production must retain the signed source
  file, authenticate the controller, and require maker-checker approval.
- No live Razorpay, bank, or accounting-system writes are performed.
- Gemini availability and output quality can vary; deterministic results remain authoritative.
