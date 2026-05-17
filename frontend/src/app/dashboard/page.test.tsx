import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

describe("DashboardPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uploads to the real V2 analyze route and renders the engineering report", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ status: "completed", analysis: analysisPayload }));
    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage />);

    selectAudioFile();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() => {
      expect(screen.getByText("Test mix is ready for review.")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v2/analyze",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
    expect(screen.getAllByText("Report ready").length).toBeGreaterThan(0);
  });

  it("shows backend errors without opening the report", async () => {
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

    render(<DashboardPage />);

    selectAudioFile("bad.txt");
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unsupported audio file extension '.txt'.",
    );
    expect(screen.queryByText("Engineering Report Dashboard")).not.toBeInTheDocument();
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
