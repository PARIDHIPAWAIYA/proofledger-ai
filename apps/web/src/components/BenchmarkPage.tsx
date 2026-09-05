import { FlaskConical, Ruler, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api, apiWithWakeRetry, formatPercent } from "../api";
import type { Benchmark, BenchmarkMetric, Calibration } from "../types";
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
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [error, setError] = useState("");
  const [waking, setWaking] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiWithWakeRetry<Benchmark>("/benchmark", (attempt, total) => {
      if (!cancelled) setWaking(`Waking the evidence API… attempt ${attempt} of ${total}`);
    })
      .then((next) => {
        if (cancelled) return;
        setWaking("");
        setBenchmark(next);
        // Calibration is supplementary: the baseline table stands without it.
        api<Calibration>("/calibration")
          .then((profile) => {
            if (!cancelled) setCalibration(profile);
          })
          .catch(() => undefined);
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!benchmark) return <LoadingState note={waking || undefined} />;

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

      {calibration && (
        <article className="panel calibration-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Split-conformal calibration</span>
              <h2>The abstention threshold is fitted, not hand-picked</h2>
            </div>
            <Ruler size={20} />
          </div>
          <p className="calibration-lede">
            {calibration.calibration_size} labelled payouts fit a minimum-confidence
            threshold at an error level of {calibration.profile.alpha}. The remaining{" "}
            {calibration.holdout_size} were never seen by the fit and report the coverage
            actually achieved.
          </p>
          <div className="calibration-metrics">
            <div>
              <small>Minimum confidence</small>
              <strong>{formatPercent(calibration.profile.minimum_confidence)}</strong>
            </div>
            <div>
              <small>Calibration coverage</small>
              <strong>{formatPercent(calibration.profile.empirical_coverage)}</strong>
            </div>
            <div>
              <small>Held-out coverage</small>
              <strong>{formatPercent(calibration.holdout_coverage)}</strong>
            </div>
            <div>
              <small>Single-candidate sets</small>
              <strong>
                {calibration.singleton_sets} / {calibration.candidate_sets.length}
              </strong>
            </div>
            <div>
              <small>Empty sets (evidence absent)</small>
              <strong>{calibration.empty_sets}</strong>
            </div>
          </div>
          <ul className="calibration-assumptions">
            {calibration.profile.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
            {calibration.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </article>
      )}

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
