import { FlaskConical, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api, formatPercent } from "../api";
import type { Benchmark, BenchmarkMetric } from "../types";
import { ErrorState, LoadingState, PageHeader } from "./Shared";

function MetricRow({ metric }: { metric: BenchmarkMetric }) {
  const winner = metric.method === "ProofLedger";
  return (
    <tr className={winner ? "benchmark-winner" : ""}>
      <td>
        <strong>{metric.method}</strong>
        {winner && <span className="winner-chip"><ShieldCheck size={12} /> selected</span>}
      </td>
      <td>{formatPercent(metric.precision)}</td>
      <td>{formatPercent(metric.recall)}</td>
      <td><strong>{formatPercent(metric.f1)}</strong></td>
      <td>{formatPercent(metric.review_rate)}</td>
      <td className={metric.incorrect_auto_approvals ? "danger-text" : "safe-text"}>
        {metric.incorrect_auto_approvals}
      </td>
    </tr>
  );
}

function BenchmarkPage() {
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Benchmark>("/benchmark")
      .then(setBenchmark)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!benchmark) return <LoadingState />;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Reproducible evaluation"
        title="Measure unsafe automation—not just matches."
        description="A high recall number can hide financially dangerous guesses. The held-out benchmark reports precision, recall, review workload, and incorrect automatic approvals separately."
      />

      <div className="benchmark-callout">
        <FlaskConical size={23} />
        <div>
          <strong>{benchmark.labeled_settlements} held-out settlement batches</strong>
          <p>Ground-truth links remain hidden from exact, fuzzy, and ProofLedger prediction logic.</p>
        </div>
      </div>

      <article className="table-panel benchmark-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Method</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>F1</th>
              <th>Human review</th>
              <th>Wrong auto-approvals</th>
            </tr>
          </thead>
          <tbody>
            <MetricRow metric={benchmark.exact} />
            <MetricRow metric={benchmark.fuzzy} />
            <MetricRow metric={benchmark.proofledger} />
          </tbody>
        </table>
      </article>

      <section className="benchmark-insights">
        <article className="insight safe-insight">
          <ShieldCheck size={22} />
          <div>
            <strong>ProofLedger’s win condition</strong>
            <p>Perfect held-out precision and recall in this deterministic scenario, with ambiguous evidence explicitly sent to review.</p>
          </div>
        </article>
        <article className="insight risk-insight">
          <TriangleAlert size={22} />
          <div>
            <strong>Why fuzzy matching is unsafe</strong>
            <p>It produces a match for every row—even when the correct bank evidence is missing—creating silent automatic errors.</p>
          </div>
        </article>
      </section>

      <div className="caveat-panel">
        <strong>Honest limitations</strong>
        <ul>
          {benchmark.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
        </ul>
      </div>
    </div>
  );
}

export default BenchmarkPage;
