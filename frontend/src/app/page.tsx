import Link from "next/link";

const workflowSteps = [
  { label: "Upload", detail: "Stage the audio file and target profile." },
  { label: "Analyze", detail: "Run deterministic metrics and reporting." },
  { label: "Master", detail: "Read the recommended chain and warnings." },
  { label: "MIDI", detail: "Generate editable MIDI from a prompt." },
  { label: "Export", detail: "Download MIDI or use report details in the DAW." },
];

export default function HomePage() {
  return (
    <main className="route-page">
      <section className="dashboard-hero">
        <div>
          <span>Dashboard</span>
          <h1>Sonic AI V2 studio</h1>
          <p>One workspace for analysis, mastering direction, and deterministic MIDI generation.</p>
        </div>
        <div className="hero-actions">
          <Link className="primary-link" href="/analysis">
            Analyze audio
          </Link>
          <Link className="secondary-link" href="/midi">
            MIDI Studio
          </Link>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">Production flow</div>
        <div className="workflow-grid">
          {workflowSteps.map((step, index) => (
            <article className="workflow-step" key={step.label}>
              <span>{index + 1}</span>
              <h2>{step.label}</h2>
              <p>{step.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
