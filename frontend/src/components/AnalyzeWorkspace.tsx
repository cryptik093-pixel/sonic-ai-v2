"use client";

import { useMemo, useState } from "react";

import { EngineeringReportDashboard } from "@/components/EngineeringReportDashboard";
import { API_ENDPOINTS, uploadFile } from "@/lib/api";
import type { AnalysisPayload, AnalyzeErrorResponse, AnalyzeResponse } from "@/types";

const targetProfiles = [
  { value: "modern_hiphop_master", label: "Modern Hip-Hop Master" },
  { value: "streaming_balanced", label: "Streaming Balanced" },
  { value: "club_trap_master", label: "Club Trap Master" },
];

type AnalyzeState = "idle" | "analyzing" | "completed" | "error";

export function AnalyzeWorkspace() {
  const maxUploadBytes = 200 * 1024 * 1024;
  const [file, setFile] = useState<File | null>(null);
  const [targetProfile, setTargetProfile] = useState(targetProfiles[0].value);
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [state, setState] = useState<AnalyzeState>("idle");
  const [error, setError] = useState<string | null>(null);

  const fileSummary = useMemo(() => {
    if (!file) {
      return "No file selected";
    }
    return `${file.name} - ${formatBytes(file.size)}`;
  }, [file]);

  async function handleAnalyze() {
    if (!file || file.size > maxUploadBytes) {
      setError("Select a supported audio file under 200 MB.");
      return;
    }

    setState("analyzing");
    setError(null);
    setAnalysis(null);

    try {
      const result = await uploadFile<AnalyzeResponse | AnalyzeErrorResponse>(
        API_ENDPOINTS.analyze,
        file,
        { target_profile: targetProfile },
      );
      if (result.status !== "completed") {
        throw new Error(result.error.message);
      }
      setAnalysis(result.analysis);
      setState("completed");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to analyze audio.");
      setState("error");
    }
  }

  return (
    <section className="analysis-workspace" aria-label="Audio analysis workspace">
      <section className="workflow-panel" aria-label="Upload and analysis controls">
        <div className="panel-heading">
          <span>Upload</span>
          <h1>Analyze a track</h1>
          <p>WAV, FLAC, AIFF, MP3, and OGG files up to 200 MB.</p>
        </div>

        <div className="upload-card">
          <label htmlFor="audio-file">Upload audio</label>
          <input
            accept=".wav,.wave,.flac,.aiff,.aif,.mp3,.ogg,audio/*"
            disabled={state === "analyzing"}
            id="audio-file"
            onChange={(event) => {
              const nextFile = event.target.files?.[0] ?? null;
              setFile(nextFile);
              setAnalysis(null);
              setError(null);
              setState("idle");
            }}
            type="file"
          />
          <div className="file-summary">{fileSummary}</div>
        </div>

        <label className="profile-control" htmlFor="target-profile">
          Target profile
          <select
            disabled={state === "analyzing"}
            id="target-profile"
            onChange={(event) => setTargetProfile(event.target.value)}
            value={targetProfile}
          >
            {targetProfiles.map((profile) => (
              <option key={profile.value} value={profile.value}>
                {profile.label}
              </option>
            ))}
          </select>
        </label>

        <button
          className="analyze-button"
          disabled={!file || state === "analyzing"}
          onClick={handleAnalyze}
        >
          {state === "analyzing" ? "Analyzing..." : "Analyze"}
        </button>

        <RunStatus state={state} />

        {error ? (
          <div className="error-message" role="alert">
            <strong>Analysis error</strong>
            <p>{error}</p>
          </div>
        ) : null}
      </section>

      <section className="result-surface" aria-busy={state === "analyzing"}>
        {analysis ? (
          <>
            <div className="result-header">
              <div>
                <span>{analysis.filename ?? "Analyzed file"}</span>
                <h2>Engineering Report</h2>
              </div>
              <div className="engine-version">{analysis.engine_version ?? "engine unavailable"}</div>
            </div>
            <EngineeringReportDashboard analysis={analysis} />
          </>
        ) : (
          <div className="empty-state">
            <span className="empty-kicker">Ready</span>
            <h2>Upload audio to generate the engineering report.</h2>
            <p>Results appear here after analysis completes.</p>
          </div>
        )}
      </section>
    </section>
  );
}

function RunStatus({ state }: { state: AnalyzeState }) {
  return (
    <div className={`run-status status-${state}`} role="status" aria-live="polite">
      <div className="run-status-topline">
        <span>Status</span>
        <strong>{statusLabel(state)}</strong>
      </div>
      <div
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={progressValue(state)}
        className="progress-track"
        role="progressbar"
      >
        <span style={{ width: `${progressValue(state)}%` }} />
      </div>
      <div className="step-copy">
        <strong>{statusLabel(state)}</strong>
        <p>{statusDetail(state)}</p>
      </div>
    </div>
  );
}

function progressValue(state: AnalyzeState) {
  if (state === "completed") {
    return 100;
  }
  if (state === "analyzing") {
    return 70;
  }
  if (state === "error") {
    return 35;
  }
  return 0;
}

function statusLabel(state: AnalyzeState) {
  if (state === "analyzing") {
    return "Running analysis";
  }
  if (state === "completed") {
    return "Report ready";
  }
  if (state === "error") {
    return "Needs attention";
  }
  return "Ready";
}

function statusDetail(state: AnalyzeState) {
  if (state === "analyzing") {
    return "Computing deterministic loudness, spectral, stereo, and report metrics.";
  }
  if (state === "completed") {
    return "Review the engineering report and mastering chain.";
  }
  if (state === "error") {
    return "Resolve the upload or backend issue, then retry.";
  }
  return "Choose a supported audio file and target profile.";
}

function formatBytes(bytes: number) {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
