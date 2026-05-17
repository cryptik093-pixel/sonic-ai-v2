import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App analysis workflow states", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("shows staged progress while analysis is running", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
    expect(screen.getByRole("progressbar", { name: "Analysis progress" })).toHaveAttribute(
      "aria-valuetext",
      "Upload received",
    );
    expect(screen.getByLabelText("Analysis running")).toBeInTheDocument();

    expect(
      screen.getAllByText("Sending the selected audio file to the analysis engine.").length,
    ).toBeGreaterThan(0);
  });

  it("renders the report and completed status after a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ status: "completed", analysis: analysisPayload })),
    );

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() => {
      expect(screen.getAllByText("Report ready").length).toBeGreaterThan(0);
    });
    expect(screen.getByRole("progressbar", { name: "Analysis progress" })).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
    expect(screen.getByText("Engineering Report Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Test mix is ready for review.")).toBeInTheDocument();
  });

  it("shows a structured retryable error state from backend JSON errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            status: "error",
            error: {
              code: "unsupported_audio_format",
              message: "Unsupported audio file extension '.txt'.",
            },
          },
          400,
        ),
      ),
    );

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("unsupported audio format");
    expect(screen.getByRole("alert")).toHaveTextContent("Unsupported audio file extension '.txt'.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(screen.getByText("The report was not generated.")).toBeInTheDocument();
  });

  it("shows a contract error when backend error JSON is malformed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ status: "error" }, 500)),
    );

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid error response");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "did not match the API contract",
    );
    expect(screen.queryByText("Engineering Report Dashboard")).not.toBeInTheDocument();
  });

  it("keeps the report closed when completed JSON is missing analysis data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ status: "completed" })),
    );

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("malformed analysis response");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "did not include a usable completed analysis payload",
    );
    expect(screen.queryByText("Engineering Report Dashboard")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("shows a retryable error when the backend returns invalid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers(),
        redirected: false,
        statusText: "OK",
        type: "basic",
        url: "",
        clone: vi.fn(),
        body: null,
        bodyUsed: false,
        json: async () => {
          throw new SyntaxError("Unexpected token");
        },
      } as unknown as Response)),
    );

    render(<App />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid json response");
    expect(screen.getByRole("alert")).toHaveTextContent("The backend response was not valid JSON.");
    expect(screen.queryByText("Engineering Report Dashboard")).not.toBeInTheDocument();
  });

  it("resets prior results when a new file is selected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ status: "completed", analysis: analysisPayload })),
    );

    render(<App />);

    selectAudioFile("mix.wav");
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("Test mix is ready for review.")).toBeInTheDocument();

    selectAudioFile("next-mix.wav");

    await waitFor(() => {
      expect(screen.queryByText("Test mix is ready for review.")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Ready for audio")).toBeInTheDocument();
  });
});

function selectAudioFile(name = "mix.wav") {
  const file = new File(["audio"], name, { type: "audio/wav" });
  const input = screen.getByLabelText("Upload audio");

  fireEvent.change(input, { target: { files: [file] } });
}

function jsonResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

const analysisPayload = {
  filename: "mix.wav",
  profile_id: "modern_hiphop_master",
  engine_version: "sonic-ai-v2-analysis-core-0.1.0",
  engineering_report: {
    summary: {
      overall_grade: "strong",
      short_verdict: "Test mix is ready for review.",
      main_issue: null,
      confidence: "high",
    },
    scorecard: {
      loudness: 92,
      dynamics: 88,
      low_end: 90,
      stereo: 95,
      spectral_balance: 87,
      translation: 90,
    },
    priority_moves: [],
    mastering_chain: {
      chain_type: "clean_master",
      recommended_chain: ["Corrective EQ", "True peak limiter"],
      warning: null,
    },
    mix_translation: {
      club_translation: "Club translation is stable.",
      phone_translation: "Phone playback is readable.",
      car_translation: "Car playback should translate.",
      mono_translation: "Mono fold-down risk is low.",
    },
    warnings: [],
    metadata: {
      deterministic: true,
      report_version: "engineering-report-0.1.0",
      limitations: ["Deterministic test report."],
    },
  },
};
