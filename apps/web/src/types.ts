export type Overview = {
  dataset_id: string;
  evidence_records: number;
  captured_paise: number;
  settled_paise: number;
  settlement_count: number;
  failed_controls: number;
  critical_exceptions: number;
  review_queue: number;
  automation_rate: number;
  graph: { objects: number; events: number; edges: number; components: number };
};

export type SettlementSummary = {
  settlement_id: string;
  occurred_at: string;
  gross_paise: number;
  fees_paise: number;
  tax_paise: number;
  refunds_paise: number;
  net_paise: number;
  bank_reference: string;
  status: "ready" | "blocked";
  failed_controls: number;
  match_tier: "exact" | "composite" | "semantic" | "unmatched";
  decision_status: string;
  confidence: number;
};

export type Control = {
  control_id: string;
  name: string;
  status: "pass" | "fail";
  severity: "info" | "warning" | "critical";
  object_ids: string[];
  evidence_ids: string[];
  expected_paise: number | null;
  observed_paise: number | null;
  difference_paise: number | null;
  explanation: string;
  remediation: string | null;
};

export type Candidate = {
  candidate_id: string;
  confidence: number;
  reasons: string[];
  amount_delta_paise: number;
  date_delta_days: number;
};

export type Decision = {
  decision_id: string;
  left_record_ids: string[];
  right_record_ids: string[];
  tier: string;
  status: string;
  confidence: number;
  reasons: string[];
  candidates: Candidate[];
  requires_human: boolean;
};

export type Review = {
  question: {
    question_id: string;
    prompt: string;
    evidence_requested: string;
    expected_information_gain: number;
    candidate_ids: string[];
  };
  decision: Decision;
  settlement: SettlementSummary | null;
  expected_bank_reference: string | null;
};

export type ReviewResolution = {
  resolution_id: string;
  question_id: string;
  decision_id: string;
  settlement_record_id: string;
  candidate_record_id: string | null;
  provided_bank_reference: string;
  provided_amount_paise: number;
  provided_occurred_at: string;
  provided_external_id: string;
  evidence_sha256: string;
  original_candidate_hash: string | null;
  actor: string;
  rationale: string;
  resolved_at: string;
  resolution_hash: string;
};

export type ReviewResolutionOutcome = {
  resolution: ReviewResolution;
  audit_verified: boolean;
  queue_before: number;
  queue_after: number;
  affected_settlements: Array<{
    settlement_id: string;
    before_status: string;
    after_status: string;
    before_decision: string;
    after_decision: string;
  }>;
  settlement: SettlementSummary;
  remaining_blockers: string[];
};

export type BenchmarkMetric = {
  method: string;
  precision: number;
  recall: number;
  f1: number;
  review_rate: number;
  incorrect_auto_approvals: number;
  predicted_links: number;
};

export type Benchmark = {
  labeled_settlements: number;
  exact: BenchmarkMetric;
  fuzzy: BenchmarkMetric;
  proofledger: BenchmarkMetric;
  caveats: string[];
};

export type Evidence = {
  record_id: string;
  source: string;
  object_type: string;
  occurred_at: string;
  amount_paise: number;
  external_id: string;
  status: string;
  source_hash: string;
};

export type JournalProposal = {
  proposal_id: string;
  status: string;
  debit_paise: number;
  credit_paise: number;
  lines: Array<{
    account_code: string;
    account_name: string;
    side: "debit" | "credit";
    amount_paise: number;
    memo: string;
  }>;
};

export type SettlementDetail = {
  summary: SettlementSummary;
  evidence: Evidence[];
  controls: Control[];
  decision: Decision;
  journal_proposal: JournalProposal;
  certificate_id: string | null;
};

export type GraphData = {
  nodes: Array<{ id: string; kind: "object" | "event"; label: string }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    relationship: string;
  }>;
};

export type IngestionSource =
  | "razorpay_settlements"
  | "bank_statement"
  | "general_ledger";

export type MappingSuggestion = {
  canonical_field: string;
  source_column: string | null;
  confidence: number;
  method: string;
  required: boolean;
};

export type IngestionPreview = {
  upload_id: string;
  source_type: IngestionSource;
  filename: string;
  file_sha256: string;
  size_bytes: number;
  row_count: number;
  headers: string[];
  sample_rows: Array<Record<string, string>>;
  suggestions: MappingSuggestion[];
  required_fields: string[];
  warnings: string[];
  expires_at: string;
};

export type IngestionManifest = {
  manifest_id: string;
  upload_id: string;
  source_type: IngestionSource;
  filename: string;
  file_sha256: string;
  size_bytes: number;
  row_count: number;
  record_count: number;
  field_mapping: Record<string, string>;
  amount_unit: "rupees" | "paise";
  record_hashes: Record<string, string>;
  imported_at: string;
  signature_algorithm: "Ed25519";
  signing_public_key: string;
  manifest_hash: string;
  signature: string;
};

export type IngestionCommitResponse = {
  manifest: IngestionManifest;
  records_preview: Evidence[];
};

export type IngestionVerification = {
  valid: boolean;
  checks: Record<string, boolean>;
  failures: string[];
};

export type AIMappingResponse = {
  mapping: Record<string, string | null>;
  generated_by: string;
  warning: string;
};
