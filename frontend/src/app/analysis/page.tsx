import { AnalyzeWorkspace } from "@/components/AnalyzeWorkspace";

export default function AnalysisPage() {
  return (
    <main className="route-page">
      <div className="route-heading">
        <span>Analysis</span>
        <h1>Audio analysis</h1>
      </div>
      <AnalyzeWorkspace />
    </main>
  );
}
