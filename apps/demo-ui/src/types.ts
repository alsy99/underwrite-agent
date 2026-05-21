export type CaseStatus = "queued" | "processing" | "completed" | "failed";
export type RecommendedAction = "approve" | "review" | "decline";
export type LoanVertical =
  | "sba_7a"
  | "cre_acquisition"
  | "specialty_mortgage_bank_statement";

export interface CaseListItem {
  case_id: string;
  status: CaseStatus;
  vertical: LoanVertical;
  tenant_id: string;
  created_at: string;
  completed_at: string | null;
  recommended_action: RecommendedAction | null;
  findings_count: number;
  contradictions_count: number;
}

export interface Citation {
  doc_id: string;
  page: number | null;
  span: string | null;
}

export interface Contradiction {
  severity: string;
  claim_a: string;
  claim_b: string;
  source_doc_ids: string[];
  confidence: number;
  quoted_evidence: string;
}

export interface PolicyFinding {
  rule_ref: string;
  status: string;
  excerpt: string;
  source_policy_doc_id: string;
  confidence: number;
}

export interface Finding {
  id: string;
  severity: string;
  title: string;
  description: string;
  citations: Citation[];
}

export interface InvestigationStep {
  step: number;
  tool: string;
  summary: string;
  timestamp: string;
}

export interface CaseFile {
  executive_summary: string;
  findings: Finding[];
  contradictions: Contradiction[];
  policy_findings: PolicyFinding[];
  investigation_timeline: InvestigationStep[];
  recommended_action: RecommendedAction;
  open_questions: string[];
}

export interface CaseResponse {
  case_id: string;
  status: CaseStatus;
  vertical: LoanVertical;
  tenant_id: string;
  created_at: string;
  completed_at: string | null;
  case_file: CaseFile | null;
  error: string | null;
}

export interface AuditEvent {
  event_id: string;
  case_id: string;
  timestamp: string;
  actor: string;
  action: string;
  inputs_hash: string | null;
  outputs: Record<string, unknown>;
  model: string | null;
  prompt_version: string | null;
}
