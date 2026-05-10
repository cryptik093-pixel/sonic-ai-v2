import { render, screen, within } from "@testing-library/react";

import { EngineeringReportDashboard } from "./EngineeringReportDashboard";
import type { AnalysisPayload } from "../types";

describe("EngineeringReportDashboard", () => {
  it("renders with a full engineering_report payload", () => {
    render(<EngineeringReportDashboard analysis={analysisWithReport()} />);

    expect(screen.getByText("Report Summary")).toBeInTheDocument();
    expect(screen.getByText("strong")).toBeInTheDocument();
    expect(screen.getAllByText("Fix mono compatibility risk").length).toBeGreaterThan(0);
    expect(screen.getByText("Mastering Chain")).toBeInTheDocument();
    expect(screen.getByText("Mix Translation")).toBeInTheDocument();
    expect(screen.getByText("engineering-report-0.1.0")).toBeInTheDocument();
  });

  it("does not crash with missing optional fields", () => {
    render(<EngineeringReportDashboard analysis={{ engineering_report: {} }} />);

    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.getByText("No summary verdict was provided.")).toBeInTheDocument();
    expect(screen.getByText("Technical analysis review")).toBeInTheDocument();
  });

  it("renders priority moves correctly", () => {
    render(<EngineeringReportDashboard analysis={analysisWithReport()} />);

    expect(screen.getAllByText("Fix mono compatibility risk").length).toBeGreaterThan(0);
    expect(screen.getByText("Inspect wideners and polarity before release.")).toBeInTheDocument();
  });

  it("renders scorecard values correctly", () => {
    render(<EngineeringReportDashboard analysis={analysisWithReport()} />);

    const loudnessMeter = screen.getByRole("meter", { name: "Loudness score" });
    expect(loudnessMeter).toHaveAttribute("aria-valuenow", "92");

    const scorePanel = screen.getByText("Scorecard").closest(".panel");
    expect(scorePanel).not.toBeNull();
    expect(within(scorePanel as HTMLElement).getByText("78")).toBeInTheDocument();
  });

  it("shows the warnings section only when warnings exist", () => {
    const { rerender } = render(<EngineeringReportDashboard analysis={analysisWithReport()} />);

    expect(screen.getByText("Warnings")).toBeInTheDocument();

    rerender(
      <EngineeringReportDashboard
        analysis={analysisWithReport({
          warnings: [],
        })}
      />,
    );

    expect(screen.queryByText("Warnings")).not.toBeInTheDocument();
  });

  it("shows a fallback message when engineering_report is missing", () => {
    render(<EngineeringReportDashboard analysis={{ filename: "mix.wav" }} />);

    expect(
      screen.getByText("Engineering report unavailable for this analysis."),
    ).toBeInTheDocument();
  });
});

function analysisWithReport(
  reportOverrides: Partial<NonNullable<AnalysisPayload["engineering_report"]>> = {},
): AnalysisPayload {
  return {
    filename: "mix.wav",
    profile_id: "modern_hiphop_master",
    engine_version: "sonic-ai-v2-analysis-core-0.1.0",
    engineering_report: {
      summary: {
        overall_grade: "strong",
        short_verdict: "The mix is close, with a few focused engineering checks recommended.",
        main_issue: "Fix mono compatibility risk",
        confidence: "high",
      },
      scorecard: {
        loudness: 92,
        dynamics: 88,
        low_end: 84,
        stereo: 78,
        spectral_balance: 87,
        translation: 86,
      },
      priority_moves: [
        {
          id: "fix_mono_compatibility",
          title: "Fix mono compatibility risk",
          domain: "stereo",
          severity: "major",
          reason: "Stereo correlation is low.",
          action: "Inspect wideners and polarity before release.",
          confidence: "high",
        },
      ],
      mastering_chain: {
        chain_type: "clean_master",
        recommended_chain: ["Corrective EQ", "Gentle bus compression", "True peak limiter"],
        warning: null,
      },
      mix_translation: {
        club_translation: "Low-end weight should translate on larger systems.",
        phone_translation: "Small speakers should remain readable.",
        car_translation: "Car playback should be a useful final check.",
        mono_translation: "Mono playback needs verification.",
      },
      warnings: [
        {
          code: "unsafe_stereo_correlation",
          message: "Stereo correlation is low enough to require mono compatibility review.",
          severity: "major",
        },
      ],
      metadata: {
        deterministic: true,
        report_version: "engineering-report-0.1.0",
        limitations: ["Report is generated from deterministic audio metrics."],
      },
      ...reportOverrides,
    },
  };
}
