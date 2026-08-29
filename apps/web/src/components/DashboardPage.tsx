import {
  ArrowRight,
  Banknote,
  CircleAlert,
  DatabaseZap,
  GitBranch,
  ScanSearch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Page } from "../App";
import { api, formatMoney, formatPercent } from "../api";
import type { Benchmark, Overview, SettlementSummary } from "../types";
import {
  ErrorState,
  LoadingState,
  Metric,
  PageHeader,
  StatusBadge,
} from "./Shared";

function DashboardPage({
  onNavigate,
}: {
  onNavigate: (page: Page) => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [settlements, setSettlements] = useState<SettlementSummary[]>([]);
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<Overview>("/overview"),
      api<SettlementSummary[]>("/settlements"),
      api<Benchmark>("/benchmark"),
    ])
      .then(([nextOverview, nextSettlements, nextBenchmark]) => {
        setOverview(nextOverview);
        setSettlements(nextSettlements);
        setBenchmark(nextBenchmark);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!overview || !benchmark) return <LoadingState />;

  const chartData = settlements.map((settlement) => ({
    id: settlement.settlement_id.replace("setl_demo_", "#"),
    net: Math.round(settlement.net_paise / 100_000) / 10,
    blocked:
      settlement.status === "blocked"
        ? Math.round(settlement.net_paise / 100_000) / 10
        : 0,
  }));
  const ready = settlements.filter((item) => item.status === "ready").length;

  return (
    <div className="page">
      <PageHeader
        eyebrow="July close · live reconstruction"
        title="Close with evidence, not confidence."
        description="Every rupee is traced from merchant order to bank and ledger. Uncertainty becomes a review question—not a guessed match."
        action={
          <button className="primary-button" onClick={() => onNavigate("settlements")}>
            Open settlement book <ArrowRight size={16} />
          </button>
        }
      />

      <section className="metric-grid">
        <Metric
          label="Captured volume"
          value={formatMoney(overview.captured_paise, true)}
          detail={overview.evidence_records.toLocaleString("en-IN") + " immutable records"}
        />
        <Metric
          label="Close ready"
          value={ready + " / " + overview.settlement_count}
          detail="settlements cleared by controls"
          tone="good"
        />
        <Metric
          label="Critical exceptions"
          value={String(overview.critical_exceptions)}
          detail="must resolve before close"
          tone="risk"
        />
        <Metric
          label="Safe automation"
          value={formatPercent(overview.automation_rate)}
          detail="semantic matches excluded"
          tone="good"
        />
      </section>

      <section className="dashboard-grid">
        <article className="panel settlement-runway">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Settlement runway</span>
              <h2>Net payout by batch</h2>
            </div>
            <div className="chart-legend">
              <span><i className="legend-safe" /> cleared</span>
              <span><i className="legend-risk" /> blocked</span>
            </div>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barGap={-16}>
                <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#e3e1da" />
                <XAxis dataKey="id" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  tickFormatter={(value) => "₹" + value + "L"}
                />
                <Tooltip
                  cursor={{ fill: "#f1efe8" }}
                  formatter={(value) => ["₹" + value + " lakh", "Net"]}
                />
                <Bar dataKey="net" fill="#1e6a55" radius={[4, 4, 0, 0]} />
                <Bar dataKey="blocked" fill="#d5664a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel control-room">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Controller attention</span>
              <h2>{overview.review_queue} evidence questions</h2>
            </div>
            <CircleAlert className="risk-icon" size={22} />
          </div>
          <div className="exception-stack">
            {settlements
              .filter((item) => item.status === "blocked")
              .slice(0, 3)
              .map((settlement) => (
                <button
                  key={settlement.settlement_id}
                  className="exception-row"
                  onClick={() => onNavigate("settlements")}
                >
                  <span className="exception-icon"><ScanSearch size={17} /></span>
                  <div>
                    <strong>{settlement.settlement_id}</strong>
                    <small>
                      {settlement.failed_controls + " failed controls · "}
                      {formatMoney(settlement.net_paise)}
                    </small>
                  </div>
                  <StatusBadge status={settlement.decision_status} />
                </button>
              ))}
          </div>
          <button className="text-button" onClick={() => onNavigate("reviews")}>
            Work the review queue <ArrowRight size={15} />
          </button>
        </article>
      </section>

      <section className="dashboard-grid lower">
        <article className="panel proof-chain">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Object-centric proof chain</span>
              <h2>One lifecycle, five source systems</h2>
            </div>
            <GitBranch size={20} />
          </div>
          <div className="chain">
            {[
              ["Order", DatabaseZap],
              ["Payment", Banknote],
              ["Settlement", Sparkles],
              ["Bank", ShieldCheck],
              ["Ledger", GitBranch],
            ].map(([label, Icon], index) => (
              <div className="chain-fragment" key={String(label)}>
                <div className="chain-node">
                  <Icon size={18} />
                  <span>{String(label)}</span>
                </div>
                {index < 4 && <ArrowRight className="chain-arrow" size={16} />}
              </div>
            ))}
          </div>
          <div className="graph-counts">
            <div><strong>{overview.graph.objects}</strong><span>objects</span></div>
            <div><strong>{overview.graph.events}</strong><span>events</span></div>
            <div><strong>{overview.graph.edges}</strong><span>evidence edges</span></div>
          </div>
        </article>

        <article className="panel benchmark-peek">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Held-out safety benchmark</span>
              <h2>Precision without silent errors</h2>
            </div>
          </div>
          <div className="score-comparison">
            {[benchmark.exact, benchmark.fuzzy, benchmark.proofledger].map((metric) => (
              <div
                key={metric.method}
                className={"score-row " + (metric.method === "ProofLedger" ? "winner" : "")}
              >
                <span>{metric.method}</span>
                <div className="score-track">
                  <i style={{ width: String(metric.f1 * 100) + "%" }} />
                </div>
                <strong>{formatPercent(metric.f1)}</strong>
              </div>
            ))}
          </div>
          <div className="benchmark-proof">
            <ShieldCheck size={18} />
            <span>
              <strong>0 incorrect auto-approvals</strong> with{" "}
              {formatPercent(benchmark.proofledger.review_rate)} sent to humans.
            </span>
          </div>
          <button className="text-button" onClick={() => onNavigate("benchmark")}>
            Inspect methodology <ArrowRight size={15} />
          </button>
        </article>
      </section>
    </div>
  );
}

export default DashboardPage;
