"use client";

import { useState } from "react";

import { API_ENDPOINTS, getConfiguredApiBaseUrl, getJSON } from "@/lib/api";

interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function checkBackend() {
    setChecking(true);
    setError(null);
    try {
      setHealth(await getJSON<HealthResponse>(API_ENDPOINTS.health));
    } catch (caught) {
      setHealth(null);
      setError(caught instanceof Error ? caught.message : "Backend health check failed.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <main className="route-page">
      <div className="route-heading">
        <span>Settings</span>
        <h1>Runtime settings</h1>
      </div>

      <section className="settings-grid">
        <article className="panel">
          <div className="section-heading">API connection</div>
          <dl className="settings-list">
            <div>
              <dt>Base URL</dt>
              <dd>{getConfiguredApiBaseUrl()}</dd>
            </div>
            <div>
              <dt>Analyze route</dt>
              <dd>{API_ENDPOINTS.analyze}</dd>
            </div>
            <div>
              <dt>MIDI route</dt>
              <dd>{API_ENDPOINTS.promptMidi}</dd>
            </div>
          </dl>
          <button className="secondary-button" disabled={checking} onClick={checkBackend}>
            {checking ? "Checking..." : "Check backend"}
          </button>
        </article>

        <article className="panel">
          <div className="section-heading">Backend status</div>
          {health ? (
            <dl className="settings-list">
              <div>
                <dt>Status</dt>
                <dd>{health.status}</dd>
              </div>
              <div>
                <dt>Service</dt>
                <dd>{health.service}</dd>
              </div>
              <div>
                <dt>Version</dt>
                <dd>{health.version}</dd>
              </div>
            </dl>
          ) : (
            <p className="subtle-copy">No health check has been run in this browser session.</p>
          )}
          {error ? (
            <div className="error-message" role="alert">
              <strong>Health check failed</strong>
              <p>{error}</p>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}
