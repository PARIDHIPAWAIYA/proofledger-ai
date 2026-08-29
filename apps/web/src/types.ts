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
