import Link from "next/link";

export default function MasteringPage() {
  return (
    <main className="route-page">
      <div className="route-heading">
        <span>Mastering</span>
        <h1>Mastering direction</h1>
      </div>

      <section className="mastering-layout">
        <article className="panel">
          <div className="section-heading">Current chain</div>
          <div className="empty-compact">
            <h2>Run analysis to populate the mastering chain.</h2>
            <p>The chain is read from the engineering report returned by the backend.</p>
            <Link className="primary-link" href="/analysis">
              Analyze audio
            </Link>
          </div>
        </article>

        <article className="panel">
          <div className="section-heading">Chain slots</div>
          <ol className="chain-steps large">
            <li>Corrective EQ</li>
            <li>Bus compression</li>
            <li>Saturation</li>
            <li>Stereo safety</li>
            <li>True peak limiter</li>
          </ol>
        </article>
      </section>
    </main>
  );
}
