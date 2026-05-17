import Link from "next/link";

export default function UploadsPage() {
  return (
    <main className="route-page">
      <div className="route-heading">
        <span>Uploads</span>
        <h1>Audio library</h1>
      </div>

      <section className="library-layout">
        <div className="panel">
          <div className="section-heading">Upload intake</div>
          <div className="empty-compact">
            <h2>No persistent library endpoint is documented yet.</h2>
            <p>Use the analysis workspace to upload a file and run the current backend contract.</p>
            <Link className="primary-link" href="/analysis">
              Open analysis
            </Link>
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">Supported files</div>
          <div className="format-list">
            {["WAV", "FLAC", "AIFF", "MP3", "OGG"].map((format) => (
              <span key={format}>{format}</span>
            ))}
          </div>
          <p className="subtle-copy">Maximum upload size: 200 MB.</p>
        </div>
      </section>
    </main>
  );
}
