import { AnalyzeWorkspace } from "@/components/AnalyzeWorkspace";

export default function DashboardPage() {
  return (
    <main className="route-page">
      <div className="route-heading">
        <span>Dashboard</span>
        <h1>Session command center</h1>
      </div>
      <AnalyzeWorkspace />
    </main>
  );
}
