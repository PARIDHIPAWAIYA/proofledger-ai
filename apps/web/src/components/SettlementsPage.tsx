import {
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  Fingerprint,
  Search,
  ShieldAlert,
  TestTube2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, formatMoney } from "../api";
import type { SettlementDetail, SettlementSummary } from "../types";
import {
  ErrorState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "./Shared";

type Verification = {
  valid: boolean;
  checks: Record<string, boolean>;
  failures: string[];
};

function SettlementsPage() {
  const [settlements, setSettlements] = useState<SettlementSummary[]>([]);
  const [selected, setSelected] = useState<SettlementDetail | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "ready" | "blocked">("all");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [certificateId, setCertificateId] = useState("");
  const [verification, setVerification] = useState<Verification | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<SettlementSummary[]>("/settlements")
      .then(setSettlements)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const filtered = useMemo(
    () =>
      settlements.filter(
        (item) =>
          (filter === "all" || item.status === filter) &&
          item.settlement_id.toLowerCase().includes(query.toLowerCase()),
      ),
    [filter, query, settlements],
  );

  const openSettlement = async (settlementId: string) => {
    setActionError("");
    setVerification(null);
    setCertificateId("");
    try {
      const detail = await api<SettlementDetail>("/settlements/" + settlementId);
      setSelected(detail);
      if (detail.certificate_id) setCertificateId(detail.certificate_id);
    } catch (reason) {
      setActionError((reason as Error).message);
    }
  };

  const issueCertificate = async () => {
    if (!selected) return;
    setBusy(true);
    setActionError("");
    try {
      const certificate = await api<{ certificate_id: string }>(
        "/settlements/" + selected.summary.settlement_id + "/certificate",
        { method: "POST" },
      );
      setCertificateId(certificate.certificate_id);
    } catch (reason) {
      setActionError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const verifyCertificate = async (simulateTamper: boolean) => {
    if (!certificateId) return;
    setBusy(true);
    setActionError("");
    try {
      const result = await api<Verification>(
        "/certificates/" + certificateId + "/verify",
        {
          method: "POST",
          body: JSON.stringify({ simulate_tamper: simulateTamper }),
        },
      );
      setVerification(result);
    } catch (reason) {
      setActionError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error) return <ErrorState message={error} />;
  if (!settlements.length) return <LoadingState />;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Settlement control book"
        title="Trace every payout to proof."
        description="Exact and composite evidence may clear automatically. Semantic evidence is visible, ranked, and always routed to a controller."
      />

      <div className="toolbar">
        <label className="search-box">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search settlement ID"
          />
        </label>
        <div className="segmented">
          {(["all", "ready", "blocked"] as const).map((item) => (
            <button
              key={item}
              className={filter === item ? "active" : ""}
              onClick={() => setFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <article className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Settlement</th>
              <th>Net payout</th>
              <th>Evidence match</th>
              <th>Controls</th>
              <th>Close state</th>
              <th aria-label="Open" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((settlement) => (
              <tr
                key={settlement.settlement_id}
                onClick={() => openSettlement(settlement.settlement_id)}
              >
                <td>
                  <strong>{settlement.settlement_id}</strong>
                  <small>{new Date(settlement.occurred_at).toLocaleDateString("en-IN")}</small>
                </td>
                <td>
                  <strong>{formatMoney(settlement.net_paise)}</strong>
                  <small>Gross {formatMoney(settlement.gross_paise)}</small>
                </td>
                <td>
                  <StatusBadge status={settlement.match_tier} />
                  <small>{Math.round(settlement.confidence * 100)}% confidence</small>
                </td>
                <td>
                  <strong>{settlement.failed_controls ? settlement.failed_controls + " failed" : "All passed"}</strong>
                  <small>10 deterministic rules</small>
                </td>
                <td><StatusBadge status={settlement.status} /></td>
                <td><ChevronRight size={17} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      {selected && (
        <div className="detail-overlay" role="dialog" aria-modal="true">
          <button className="drawer-scrim" onClick={() => setSelected(null)} aria-label="Close" />
          <aside className="detail-drawer">
            <div className="drawer-head">
              <div>
                <span className="panel-kicker">Settlement proof file</span>
                <h2>{selected.summary.settlement_id}</h2>
              </div>
              <button className="icon-button" onClick={() => setSelected(null)}>
                <X size={19} />
              </button>
            </div>

            <div className="drawer-summary">
              <div>
                <span>Net payout</span>
                <strong>{formatMoney(selected.summary.net_paise)}</strong>
              </div>
              <StatusBadge status={selected.summary.status} />
            </div>

            <section className="proof-section">
              <div className="section-title">
                <Fingerprint size={17} />
                <h3>Evidence lineage</h3>
                <span>{selected.evidence.length} records</span>
              </div>
              <div className="evidence-list">
                {selected.evidence.slice(0, 8).map((record) => (
                  <div className="evidence-row" key={record.record_id}>
                    <span className="source-code">{record.source.slice(0, 3).toUpperCase()}</span>
                    <div>
                      <strong>{record.external_id}</strong>
                      <small>{record.object_type} · {record.source_hash.slice(0, 12)}…</small>
                    </div>
                    <span>{formatMoney(record.amount_paise)}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="proof-section">
              <div className="section-title">
                <ShieldAlert size={17} />
                <h3>Control assertions</h3>
              </div>
              <div className="control-list">
                {selected.controls.map((control) => (
                  <div className="control-row" key={control.control_id}>
                    {control.status === "pass" ? (
                      <CheckCircle2 className="safe-icon" size={17} />
                    ) : (
                      <ShieldAlert className="risk-icon" size={17} />
                    )}
                    <div>
                      <strong>{control.control_id} · {control.name}</strong>
                      <small>{control.explanation}</small>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="proof-section">
              <div className="section-title">
                <FileCheck2 size={17} />
                <h3>Balanced journal proposal</h3>
                <StatusBadge status={selected.journal_proposal.status} />
              </div>
              <div className="journal-grid">
                {selected.journal_proposal.lines.map((line) => (
                  <div className="journal-line" key={line.account_code}>
                    <span>{line.account_code} · {line.account_name}</span>
                    <strong className={line.side}>{line.side} {formatMoney(line.amount_paise)}</strong>
                  </div>
                ))}
              </div>
              <div className="balance-line">
                <span>Debits = Credits</span>
                <strong>{formatMoney(selected.journal_proposal.debit_paise)}</strong>
              </div>
            </section>

            <section className="certificate-box">
              <div>
                <span className="panel-kicker">Proof-carrying close</span>
                <h3>Settlement certificate</h3>
                <p>Hashes the evidence, equation, and passed controls into one independently verifiable artifact.</p>
              </div>
              {!certificateId ? (
                <button
                  className="primary-button"
                  onClick={issueCertificate}
                  disabled={busy}
                >
                  Issue certificate
                </button>
              ) : (
                <div className="certificate-actions">
                  <button className="secondary-button" onClick={() => verifyCertificate(false)} disabled={busy}>
                    <CheckCircle2 size={15} /> Verify
                  </button>
                  <button className="danger-button" onClick={() => verifyCertificate(true)} disabled={busy}>
                    <TestTube2 size={15} /> Change ₹1
                  </button>
                </div>
              )}
              {actionError && <div className="inline-error">{actionError}</div>}
              {verification && (
                <div className={verification.valid ? "verification valid" : "verification invalid"}>
                  {verification.valid ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
                  <div>
                    <strong>{verification.valid ? "Certificate valid" : "Tampering detected"}</strong>
                    <small>
                      {verification.valid
                        ? "All hashes and financial assertions passed."
                        : "Failed: " + verification.failures.join(", ")}
                    </small>
                  </div>
                </div>
              )}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}

export default SettlementsPage;
