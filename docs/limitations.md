# Limitations

- Synthetic data cannot reproduce every production settlement behavior.
- Candidate-set coverage depends on the calibration and evaluation distributions.
- Proposed journals require professional accounting review before any production use.
- The prototype does not implement authentication or multi-tenant isolation.
- CSV uploads and signed manifests are stored in process memory and disappear on restart.
- Imported evidence is validated and signed but does not yet replace or merge into the synthetic
  dashboard workspace.
- The ingestion signer uses an ephemeral process key. Its self-contained public key detects
  mutation but is not an externally trusted merchant identity; production requires KMS/HSM keys,
  rotation, and verifier pinning.
- The review demo fingerprints an attachment but does not retain it. Production must retain the
  encrypted source file, authenticate the controller, and require maker-checker approval.
- No live Razorpay, bank, or accounting-system writes are performed.
- Gemini availability and output quality can vary; deterministic results remain authoritative.
