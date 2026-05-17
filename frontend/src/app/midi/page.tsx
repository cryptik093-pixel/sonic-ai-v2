"use client";

import { useEffect, useMemo, useState } from "react";

import { API_ENDPOINTS, postBinary } from "@/lib/api";
import type { PromptMidiRequest } from "@/types";

const styleOptions = ["trap", "drill", "house", "boom bap", "ambient"];
const keyOptions = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const modeOptions = ["minor", "major", "dorian", "phrygian"];

interface MidiDownload {
  url: string;
  fileName: string;
  byteLength: number;
  metadata: {
    prompt: string;
    seed: string;
    key: string;
    mode: string;
  };
}

export default function MidiPage() {
  const [prompt, setPrompt] = useState("dark trap melody with offbeat bass");
  const [tempo, setTempo] = useState(140);
  const [musicalKey, setMusicalKey] = useState("D");
  const [mode, setMode] = useState("minor");
  const [style, setStyle] = useState(styleOptions[0]);
  const [bars, setBars] = useState(8);
  const [seed, setSeed] = useState("42");
  const [download, setDownload] = useState<MidiDownload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const backendPrompt = useMemo(
    () => `${prompt.trim()} at ${tempo} bpm in ${musicalKey} ${mode}, ${style}, ${bars} bars`,
    [bars, mode, musicalKey, prompt, style, tempo],
  );

  useEffect(() => {
    return () => {
      if (download?.url) {
        URL.revokeObjectURL(download.url);
      }
    };
  }, [download?.url]);

  async function handleGenerate() {
    if (!prompt.trim()) {
      setError("Enter a prompt before generating MIDI.");
      return;
    }

    const parsedSeed = seed.trim() ? Number(seed) : null;
    if (parsedSeed !== null && !Number.isInteger(parsedSeed)) {
      setError("Seed must be a whole number.");
      return;
    }

    setLoading(true);
    setError(null);
    if (download?.url) {
      URL.revokeObjectURL(download.url);
    }
    setDownload(null);

    try {
      const request: PromptMidiRequest = {
        prompt: backendPrompt,
        seed: parsedSeed,
      };
      const response = await postBinary(API_ENDPOINTS.promptMidi, request);
      const url = URL.createObjectURL(response.blob);
      setDownload({
        url,
        fileName: "sonic-ai-v2-generated.mid",
        byteLength: response.blob.size,
        metadata: {
          prompt: response.headers.get("X-Prompt") ?? backendPrompt,
          seed: response.headers.get("X-Seed") ?? String(parsedSeed ?? ""),
          key: response.headers.get("X-Key") ?? musicalKey,
          mode: response.headers.get("X-Mode") ?? mode,
        },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to generate MIDI.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="route-page">
      <div className="route-heading">
        <span>MIDI Studio</span>
        <h1>Prompt-to-MIDI generation</h1>
      </div>

      <section className="midi-layout">
        <section className="tool-panel" aria-label="Prompt to MIDI controls">
          <label className="field-control" htmlFor="midi-prompt">
            Prompt
            <textarea
              id="midi-prompt"
              onChange={(event) => setPrompt(event.target.value)}
              rows={5}
              value={prompt}
            />
          </label>

          <div className="control-grid">
            <label className="field-control" htmlFor="tempo">
              Tempo
              <input
                id="tempo"
                max={220}
                min={40}
                onChange={(event) => setTempo(Number(event.target.value))}
                type="number"
                value={tempo}
              />
            </label>

            <label className="field-control" htmlFor="musical-key">
              Key
              <select
                id="musical-key"
                onChange={(event) => setMusicalKey(event.target.value)}
                value={musicalKey}
              >
                {keyOptions.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-control" htmlFor="mode">
              Mode
              <select id="mode" onChange={(event) => setMode(event.target.value)} value={mode}>
                {modeOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-control" htmlFor="bars">
              Bars
              <input
                id="bars"
                max={32}
                min={2}
                onChange={(event) => setBars(Number(event.target.value))}
                type="number"
                value={bars}
              />
            </label>
          </div>

          <label className="field-control" htmlFor="style">
            Style
            <select id="style" onChange={(event) => setStyle(event.target.value)} value={style}>
              {styleOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="field-control" htmlFor="seed">
            Seed
            <input id="seed" onChange={(event) => setSeed(event.target.value)} value={seed} />
          </label>

          <div className="prompt-preview">
            <span>Backend prompt</span>
            <p>{backendPrompt}</p>
          </div>

          <button className="analyze-button" disabled={loading || !prompt.trim()} onClick={handleGenerate}>
            {loading ? "Generating..." : "Generate MIDI"}
          </button>

          {error ? (
            <div className="error-message" role="alert">
              <strong>MIDI generation error</strong>
              <p>{error}</p>
            </div>
          ) : null}
        </section>

        <section className="panel midi-result" aria-label="Generated MIDI result">
          <div className="section-heading">Generated MIDI</div>
          {download ? (
            <>
              <dl>
                <div>
                  <dt>Prompt</dt>
                  <dd>{download.metadata.prompt}</dd>
                </div>
                <div>
                  <dt>Key / Mode</dt>
                  <dd>
                    {download.metadata.key} {download.metadata.mode}
                  </dd>
                </div>
                <div>
                  <dt>Seed</dt>
                  <dd>{download.metadata.seed || "None"}</dd>
                </div>
                <div>
                  <dt>Bytes</dt>
                  <dd>{download.byteLength}</dd>
                </div>
              </dl>
              <a className="primary-link" download={download.fileName} href={download.url}>
                Download .mid
              </a>
            </>
          ) : (
            <div className="empty-compact">
              <h2>No MIDI generated yet.</h2>
              <p>Generated files appear here for download.</p>
            </div>
          )}
        </section>

        <section className="panel audio-midi-panel" aria-label="Audio to MIDI conversion">
          <div className="section-heading">Audio-to-MIDI</div>
          <div className="empty-compact">
            <h2>Public conversion route needed.</h2>
            <p>No documented FastAPI route exists for browser audio-to-MIDI conversion.</p>
          </div>
          <label className="upload-card disabled-control" htmlFor="audio-midi-file">
            Audio source
            <input disabled id="audio-midi-file" type="file" />
            <span>Route unavailable</span>
          </label>
        </section>
      </section>
    </main>
  );
}
