# Limitations

- Synthetic data cannot reproduce every production settlement behavior.
- Candidate-set coverage depends on the calibration and evaluation distributions.
- Proposed journals require professional accounting review before any production use.
- The prototype does not implement authentication or multi-tenant isolation.
- Temporary CSV previews are stored in process memory and expire after 30 minutes. Committed
  manifests, normalized records, and ordered activation events are database-backed.
- Review resolutions and issued close certificates still disappear on restart.
- Activated imports participate in the controller workspace, but the supplied controller identity
  is not authenticated and there is no maker-checker role enforcement.
- Import activation adds evidence; it does not implement full source-period replacement, versioned
  corrections, or connector watermarks.
- The ingestion signer uses an ephemeral process key. Its self-contained public key detects
  mutation but is not an externally trusted merchant identity; production requires KMS/HSM keys,
  rotation, and verifier pinning.
- The review demo fingerprints an attachment but does not retain it. Production must retain the
  encrypted source file, authenticate the controller, and require maker-checker approval.
- No live Razorpay, bank, or accounting-system writes are performed.
- Gemini availability and output quality can vary; deterministic results remain authoritative.
