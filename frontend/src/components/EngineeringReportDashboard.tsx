import type {
  AnalysisPayload,
  EngineeringReport,
  ReportConfidence,
  ReportMove,
  ReportSeverity,
  ReportWarning,
} from "../types";

interface EngineeringReportDashboardProps {
  analysis?: AnalysisPayload | null;
}

const scoreLabels: Array<[keyof NonNullable<EngineeringReport["scorecard"]>, string]> = [
  ["loudness", "Loudness"],
  ["dynamics", "Dynamics"],
  ["low_end", "Low End"],
  ["stereo", "Stereo"],
  ["spectral_balance", "Spectral Balance"],
  ["translation", "Translation"],
];

const translationLabels: Array<[keyof NonNullable<EngineeringReport["mix_translation"]>, string]> = [
  ["club_translation", "Club"],
  ["phone_translation", "Phone"],
  ["car_translation", "Car"],
  ["mono_translation", "Mono"],
];

export function EngineeringReportDashboard({ analysis }: EngineeringReportDashboardProps) {
  const report = analysis?.engineering_report;

  if (!report) {
    return (
      <section className="empty-report" aria-label="Engineering report unavailable">
        Engineering report unavailable for this analysis.
      </section>
    );
  }

  const summary = report.summary;
  const scorecard = report.scorecard;
  const moves = report.priority_moves ?? [];
  const chain = report.mastering_chain;
  const translations = report.mix_translation;
  const warnings = report.warnings ?? [];
  const metadata = report.metadata;

  return (
    <section className="report-dashboard" aria-label="Engineering report dashboard">
      <div className="report-grid">
        <article className="panel summary-panel">
          <div className="section-heading">
            <span>Report Summary</span>
            <StatusPill value={summary?.confidence ?? "low"} tone="confidence" />
          </div>
          <div className="grade-row">
            <div>
              <div className="grade-value">{formatToken(summary?.overall_grade ?? "unknown")}</div>
              <p>{summary?.short_verdict ?? "No summary verdict was provided."}</p>
            </div>
          </div>
          {summary?.main_issue ? (
            <div className="main-issue">
              <span>Main issue</span>
              <strong>{summary.main_issue}</strong>
            </div>
          ) : null}
        </article>

        <article className="panel score-panel">
          <div className="section-heading">Scorecard</div>
          <div className="score-grid">
            {scoreLabels.map(([key, label]) => (
              <ScoreMeter key={key} label={label} value={scorecard?.[key]} />
            ))}
          </div>
        </article>

        <article className="panel moves-panel">
          <div className="section-heading">Priority Moves</div>
          {moves.length > 0 ? (
            <div className="move-list">
              {moves.map((move, index) => (
                <PriorityMoveCard key={move.id ?? `${move.title}-${index}`} move={move} />
              ))}
            </div>
          ) : (
            <p className="subtle-copy">No priority moves were returned for this analysis.</p>
          )}
        </article>

        <article className="panel chain-panel">
          <div className="section-heading">
            <span>Mastering Chain</span>
            <span className="chain-type">{formatToken(chain?.chain_type ?? "unknown")}</span>
          </div>
          <ol className="chain-steps">
            {(chain?.recommended_chain ?? ["Technical analysis review"]).map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          {chain?.warning ? <div className="chain-warning">{chain.warning}</div> : null}
        </article>

        <article className="panel translation-panel">
          <div className="section-heading">Mix Translation</div>
          <div className="translation-grid">
            {translationLabels.map(([key, label]) => (
              <div className="translation-note" key={key}>
                <span>{label}</span>
                <p>{translations?.[key] ?? "Translation note unavailable."}</p>
              </div>
            ))}
          </div>
        </article>

        {warnings.length > 0 ? (
          <article className="panel warning-panel">
            <div className="section-heading">Warnings</div>
            <div className="warning-list">
              {warnings.map((warning, index) => (
                <WarningRow key={warning.code ?? index} warning={warning} />
              ))}
            </div>
          </article>
        ) : null}

        <article className="panel metadata-panel">
          <div className="section-heading">Metadata</div>
          <dl>
            <div>
              <dt>Deterministic</dt>
              <dd>{metadata?.deterministic ? "Yes" : "Unknown"}</dd>
            </div>
            <div>
              <dt>Report Version</dt>
              <dd>{metadata?.report_version ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Target Profile</dt>
              <dd>{analysis?.profile_id ?? "Unavailable"}</dd>
            </div>
          </dl>
          {metadata?.limitations?.length ? (
            <ul className="limitations">
              {metadata.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          ) : null}
        </article>
      </div>
    </section>
  );
}

function ScoreMeter({ label, value }: { label: string; value?: number }) {
  const score = clampScore(value);

  return (
    <div className="score-meter">
      <div className="score-topline">
        <span>{label}</span>
        <strong>{score}</strong>
      </div>
      <div
        className="score-track"
        role="meter"
        aria-label={`${label} score`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
      >
        <span style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function PriorityMoveCard({ move }: { move: ReportMove }) {
  return (
    <article className={`move-card severity-${move.severity ?? "minor"}`}>
      <div className="move-card-header">
        <div>
          <h3>{move.title ?? "Untitled move"}</h3>
          <span>{formatToken(move.domain ?? "unknown")}</span>
        </div>
        <StatusPill value={move.severity ?? "minor"} tone="severity" />
      </div>
      <p>{move.reason ?? "No measured reason was provided."}</p>
      <div className="action-block">
        <span>Action</span>
        <strong>{move.action ?? "Manual engineering review recommended."}</strong>
      </div>
      <div className="move-confidence">
        Confidence: {formatToken(move.confidence ?? "low")}
      </div>
    </article>
  );
}

function WarningRow({ warning }: { warning: ReportWarning }) {
  return (
    <div className={`warning-row severity-${warning.severity ?? "minor"}`}>
      <StatusPill value={warning.severity ?? "minor"} tone="severity" />
      <div>
        <strong>{formatToken(warning.code ?? "warning")}</strong>
        <p>{warning.message ?? "Warning detail unavailable."}</p>
      </div>
    </div>
  );
}

function StatusPill({
  value,
  tone,
}: {
  value: ReportSeverity | ReportConfidence;
  tone: "severity" | "confidence";
}) {
  return <span className={`status-pill ${tone}-${value}`}>{formatToken(value)}</span>;
}

function clampScore(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function formatToken(value: string) {
  return value.replaceAll("_", " ");
}
