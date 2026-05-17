import Link from "next/link";

export default function AgentPage() {
  return (
    <main className="route-page">
      <section className="tool-panel narrow">
        <span>Agent</span>
        <h1>Assistant tools</h1>
        <p>
          No public Agent API route is documented in the current backend contract. The live
          browser tools are analysis and prompt-to-MIDI generation.
        </p>
        <div className="action-row">
          <Link className="primary-link" href="/dashboard">
            Analyze audio
          </Link>
          <Link className="secondary-link" href="/midi">
            Generate MIDI
          </Link>
        </div>
      </section>
    </main>
  );
}
