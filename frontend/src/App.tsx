import { useEffect, useMemo, useState } from "react";

import { EngineeringReportDashboard } from "./components/EngineeringReportDashboard";
import type { AnalysisPayload, AnalyzeErrorResponse, AnalyzeResponse } from "./types";

type AnalyzeState = "idle" | "analyzing" | "completed" | "error";

interface AnalysisError {
  code: string;
  message: string;
}

const targetProfiles = [
  { value: "modern_hiphop_master", label: "Modern Hip-Hop Master" },
  { value: "streaming_balanced", label: "Streaming Balanced" },
  { value: "club_trap_master", label: "Club Trap Master" },
];

const analysisSteps = [
  { label: "Upload received", detail: "Sending the selected audio file to the analysis engine." },
  { label: "Reading audio", detail: "Loading the file and validating the supported audio format." },
  { label: "Measuring mix", detail: "Computing deterministic loudness, dynamics, stereo, and spectrum metrics." },
  { label: "Preparing report", detail: "Building the engineering report from measured results." },
];

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function App() {
  const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileTooLarge, setFileTooLarge] = useState(false);
  const [targetProfile, setTargetProfile] = useState(targetProfiles[0].value);
  const [state, setState] = useState<AnalyzeState>("idle");
  const [activeStep, setActiveStep] = useState(0);
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [error, setError] = useState<AnalysisError | null>(null);

  const canAnalyze = Boolean(selectedFile) && !fileTooLarge && state !== "analyzing";
  const isAnalyzing = state === "analyzing";
  const progressValue =
    state === "completed"
      ? 100
      : state === "analyzing"
        ? Math.min(90, Math.round(((activeStep + 1) / analysisSteps.length) * 90))
        : state === "error"
          ? Math.max(25, Math.round(((activeStep + 1) / analysisSteps.length) * 90))
          : 0;
  const fileSummary = useMemo(() => {
    if (!selectedFile) {
      return "No file selected";
    }
    if (fileTooLarge) {
      return `${selectedFile.name} - ${formatBytes(selectedFile.size)} (too large)`;
    }
    return `${selectedFile.name} - ${formatBytes(selectedFile.size)}`;
  }, [selectedFile, fileTooLarge]);

  useEffect(() => {
    if (state !== "analyzing") {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setActiveStep((currentStep) => Math.min(currentStep + 1, analysisSteps.length - 1));
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, [state]);

  async function analyzeFile() {
    if (!selectedFile) {
      return;
    }

    setState("analyzing");
    setActiveStep(0);
    setError(null);
    setAnalysis(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("target_profile", targetProfile);

    try {
      const response = await fetch(`${apiBaseUrl}/api/v2/analyze`, {
        method: "POST",
        body: formData,
      });
      const payload = await readAnalyzePayload(response);
      if (!response.ok || payload.status === "error") {
        throw normalizeAnalyzeError(payload, response.status);
      }
      if (!isCompletedAnalyzePayload(payload)) {
        throw new AnalyzeRequestError(
          "malformed_analysis_response",
          "The backend returned JSON, but it did not include a usable completed analysis payload.",
        );
      }
      setAnalysis(payload.analysis);
      setActiveStep(analysisSteps.length - 1);
      setState("completed");
    } catch (caught) {
      setError(
        caught instanceof AnalyzeRequestError
          ? { code: caught.code, message: caught.message }
          : { code: "network_error", message: "Analysis failed before the backend returned JSON." },
      );
      setState("error");
    }
  }

  return (
    <main className="app-shell">
      <section className="workflow-panel" aria-label="Upload and analyze workflow">
        <div className="brand-block">
          <div className="brand-mark">S</div>
          <div>
            <h1>Sonic AI V2</h1>
            <p>Deterministic audio analysis for engineering decisions.</p>
          </div>
        </div>

        <div className="upload-card">
          <label htmlFor="audio-file">Upload audio</label>
          <input
            id="audio-file"
            type="file"
            accept=".wav,.wave,.flac,.aiff,.aif,.mp3,.ogg,audio/*"
            disabled={isAnalyzing}
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setSelectedFile(file);
              // client-side size check to avoid sending oversized files
              if (file && file.size > MAX_UPLOAD_BYTES) {
                setFileTooLarge(true);
                setError({ code: "file_too_large", message: "Selected file exceeds the 200 MB upload limit." });
                setAnalysis(null);
                setState("idle");
                setActiveStep(0);
                return;
              }
              setFileTooLarge(false);
              setError(null);
              setAnalysis(null);
              setState("idle");
              setActiveStep(0);
            }}
          />
          <div className="file-summary">{fileSummary}</div>
        </div>

        <label className="profile-control" htmlFor="target-profile">
          Target profile
          <select
            id="target-profile"
            value={targetProfile}
            disabled={isAnalyzing}
            onChange={(event) => setTargetProfile(event.target.value)}
          >
            {targetProfiles.map((profile) => (
              <option key={profile.value} value={profile.value}>
                {profile.label}
              </option>
            ))}
          </select>
        </label>

        <button className="analyze-button" disabled={!canAnalyze} onClick={analyzeFile}>
          {state === "analyzing" ? "Analyzing..." : state === "error" ? "Try again" : "Analyze"}
        </button>

        <RunStatus state={state} activeStep={activeStep} progressValue={progressValue} />

        {error ? <ErrorPanel error={error} /> : null}
      </section>

      <section className="result-surface" aria-busy={isAnalyzing}>
        {analysis ? (
          <>
            <div className="result-header">
              <div>
                <span>{analysis.filename ?? "Analyzed file"}</span>
                <h2>Engineering Report Dashboard</h2>
              </div>
              <div className="engine-version">{analysis.engine_version ?? "engine unavailable"}</div>
            </div>
            <EngineeringReportDashboard analysis={analysis} />
          </>
        ) : isAnalyzing ? (
          <LoadingState activeStep={activeStep} />
        ) : error ? (
          <div className="empty-state error-empty-state">
            <span className="empty-kicker">Analysis stopped</span>
            <h2>The report was not generated.</h2>
            <p>Resolve the upload issue shown in the workflow panel, then run the analysis again.</p>
          </div>
        ) : (
          <div className="empty-state">
            <span className="empty-kicker">Ready for audio</span>
            <h2>Upload audio to generate the engineering report.</h2>
            <p>
              The dashboard appears only after `/api/v2/analyze` returns a real
              `analysis.engineering_report` payload.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

function RunStatus({
  state,
  activeStep,
  progressValue,
}: {
  state: AnalyzeState;
  activeStep: number;
  progressValue: number;
}) {
  const currentStep = analysisSteps[activeStep];

  return (
    <div className={`run-status status-${state}`} role="status" aria-live="polite">
      <div className="run-status-topline">
        <span>Status</span>
        <strong>{formatStatus(state)}</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Analysis progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressValue}
        aria-valuetext={
          state === "analyzing" ? currentStep.label : state === "completed" ? "Report ready" : formatStatus(state)
        }
      >
        <span style={{ width: `${progressValue}%` }} />
      </div>
      <div className="step-copy">
        <strong>{state === "analyzing" ? currentStep.label : formatStatus(state)}</strong>
        <p>{state === "analyzing" ? currentStep.detail : statusDetail(state)}</p>
      </div>
    </div>
  );
}

function LoadingState({ activeStep }: { activeStep: number }) {
  const currentStep = analysisSteps[activeStep];

  return (
    <div className="loading-state" aria-label="Analysis running">
      <div className="loading-orbit" aria-hidden="true">
        <span />
      </div>
      <span className="empty-kicker">Deterministic analysis running</span>
      <h2>{currentStep.label}</h2>
      <p>{currentStep.detail}</p>
      <ol className="analysis-step-list">
        {analysisSteps.map((step, index) => (
          <li
            className={
              index < activeStep
                ? "step-complete"
                : index === activeStep
                  ? "step-active"
                  : "step-pending"
            }
            key={step.label}
          >
            <span>{index + 1}</span>
            <strong>{step.label}</strong>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ErrorPanel({ error }: { error: AnalysisError }) {
  return (
    <div className="error-message" role="alert">
      <div>
        <span>Error</span>
        <strong>{formatToken(error.code)}</strong>
      </div>
      <p>{error.message}</p>
      <p className="error-hint">Use a supported audio file under 200 MB, then retry the analysis.</p>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (!bytes) {
    return "0 KB";
  }
  const megabytes = bytes / (1024 * 1024);
  if (megabytes >= 1) {
    return `${megabytes.toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function formatStatus(state: AnalyzeState) {
  if (state === "idle") {
    return "Ready";
  }
  if (state === "analyzing") {
    return "Running deterministic analysis";
  }
  if (state === "completed") {
    return "Report ready";
  }
  return "Needs attention";
}

function statusDetail(state: AnalyzeState) {
  if (state === "idle") {
    return "Choose a supported audio file and target profile.";
  }
  if (state === "completed") {
    return "The engineering report is ready for review.";
  }
  if (state === "error") {
    return "The backend returned an error or the request could not complete.";
  }
  return "Analysis is in progress.";
}

function normalizeAnalyzeError(
  payload: AnalyzeResponse | AnalyzeErrorResponse,
  statusCode: number,
) {
  if (payload.status === "error") {
    const code = payload.error?.code;
    const message = payload.error?.message;
    if (typeof code === "string" && typeof message === "string") {
      return new AnalyzeRequestError(code, message);
    }
    return new AnalyzeRequestError(
      "invalid_error_response",
      "The backend returned an error response that did not match the API contract.",
    );
  }
  return new AnalyzeRequestError(
    "analysis_failed",
    `Analysis failed with HTTP status ${statusCode}.`,
  );
}

async function readAnalyzePayload(response: Response): Promise<AnalyzeResponse | AnalyzeErrorResponse> {
  try {
    return (await response.json()) as AnalyzeResponse | AnalyzeErrorResponse;
  } catch {
    throw new AnalyzeRequestError(
      "invalid_json_response",
      "The backend response was not valid JSON.",
    );
  }
}

function isCompletedAnalyzePayload(
  payload: AnalyzeResponse | AnalyzeErrorResponse,
): payload is AnalyzeResponse {
  return (
    payload.status === "completed" &&
    typeof payload.analysis === "object" &&
    payload.analysis !== null &&
    typeof payload.analysis.engineering_report === "object" &&
    payload.analysis.engineering_report !== null
  );
}

function formatToken(value: string) {
  return value.replaceAll("_", " ");
}

class AnalyzeRequestError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export default App;
