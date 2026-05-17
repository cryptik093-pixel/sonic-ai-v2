import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import MidiPage from "./page";

describe("MidiPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("posts to the real prompt MIDI route and exposes a MIDI download", async () => {
    const fetchMock = vi.fn(async () => midiResponse());
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:sonic-midi"),
      revokeObjectURL: vi.fn(),
    });

    render(<MidiPage />);

    fireEvent.click(screen.getByRole("button", { name: "Generate MIDI" }));

    const download = await screen.findByRole("link", { name: "Download .mid" });
    expect(download).toHaveAttribute("href", "blob:sonic-midi");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v2/prompt-midi",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "audio/midi",
        }),
      }),
    );
    expect(screen.getByText("D minor")).toBeInTheDocument();
  });
});

function midiResponse(status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) => {
        const values: Record<string, string> = {
          "X-Prompt": "dark trap melody with offbeat bass at 140 bpm in D minor",
          "X-Seed": "42",
          "X-Key": "D",
          "X-Mode": "minor",
        };
        return values[name] ?? null;
      },
    },
    blob: async () => new Blob(["midi"], { type: "audio/midi" }),
  } as Response;
}
