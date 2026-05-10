export type ReportGrade = "excellent" | "strong" | "needs_work" | "problematic" | "unknown";
export type ReportConfidence = "high" | "medium" | "low";
export type ReportSeverity = "critical" | "major" | "minor";

export interface ReportSummary {
  overall_grade?: ReportGrade;
  short_verdict?: string;
  main_issue?: string | null;
  confidence?: ReportConfidence;
}

export interface ReportScorecard {
  loudness?: number;
  dynamics?: number;
  low_end?: number;
  stereo?: number;
  spectral_balance?: number;
  translation?: number;
}

export interface ReportMove {
  id?: string;
  title?: string;
  domain?: string;
  severity?: ReportSeverity;
  reason?: string;
  action?: string;
  confidence?: ReportConfidence;
}

export interface MasteringChainRecommendation {
  chain_type?: "clean_master" | "loud_modern_master" | "corrective_mix_prep" | "unknown";
  recommended_chain?: string[];
  warning?: string | null;
}

export interface MixTranslationNotes {
  club_translation?: string;
  phone_translation?: string;
  car_translation?: string;
  mono_translation?: string;
}

export interface ReportWarning {
  code?: string;
  message?: string;
  severity?: ReportSeverity;
}

export interface ReportMetadata {
  deterministic?: boolean;
  report_version?: string;
  limitations?: string[];
}

export interface EngineeringReport {
  summary?: ReportSummary;
  scorecard?: ReportScorecard;
  priority_moves?: ReportMove[];
  mastering_chain?: MasteringChainRecommendation;
  mix_translation?: MixTranslationNotes;
  warnings?: ReportWarning[];
  metadata?: ReportMetadata;
}

export interface AnalysisPayload {
  engine_version?: string;
  filename?: string;
  profile_id?: string;
  metrics?: Record<string, unknown>;
  reference_comparison?: Record<string, unknown>;
  engineering_report?: EngineeringReport;
}

export interface AnalyzeResponse {
  status: "completed";
  analysis: AnalysisPayload;
}

export interface AnalyzeErrorResponse {
  status: "error";
  error: {
    code: string;
    message: string;
  };
}
