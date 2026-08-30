import {
  Bot,
  CheckCircle2,
  Download,
  FileKey2,
  FlaskConical,
  ShieldCheck,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type {
  AIMappingResponse,
  IngestionCommitResponse,
  IngestionManifest,
  IngestionPreview,
  IngestionSource,
  IngestionVerification,
} from "../types";
import { PageHeader } from "./Shared";

const DEMO_BANK_CSV = `Transaction ID,Value Date,Credit Amount,UTR,Description
bank_demo_001,18/07/2026,1250.50,UTR-DEMO-1001,Razorpay settlement
bank_demo_002,19/07/2026,999.00,UTR-DEMO-1002,Razorpay settlement
bank_demo_003,20/07/2026,4320.75,UTR-DEMO-1003,Razorpay settlement
`;

const SOURCE_LABELS: Record<IngestionSource, string> = {
  razorpay_settlements: "Razorpay settlements",
  bank_statement: "Bank statement",
  general_ledger: "General ledger",
};

function shortHash(value: string) {
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function DataIntakePage() {
  const [source, setSource] = useState<IngestionSource>("bank_statement");
  const [preview, setPreview] = useState<IngestionPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [unit, setUnit] = useState<"rupees" | "paise">("rupees");
  const [confirmed, setConfirmed] = useState(false);
  const [manifest, setManifest] = useState<IngestionManifest | null>(null);
  const [manifests, setManifests] = useState<IngestionManifest[]>([]);
  const [verification, setVerification] = useState<IngestionVerification | null>(null);
  const [aiNote, setAiNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const loadManifests = () =>
    api<IngestionManifest[]>("/ingestion/manifests")
      .then(setManifests)
      .catch(() => undefined);

  useEffect(() => {
    void loadManifests();
  }, []);

  const upload = async (file: File) => {
    setBusy("preview");
    setError("");
    setManifest(null);
    setVerification(null);
    setConfirmed(false);
    try {
      const form = new FormData();
      form.append("file", file);
      const next = await api<IngestionPreview>(
        `/ingestion/preview?source_type=${source}`,
        { method: "POST", body: form },
      );
      setPreview(next);
      setMapping(
        Object.fromEntries(
          next.suggestions
            .filter((item) => item.source_column)
            .map((item) => [item.canonical_field, item.source_column as string]),
        ),
      );
      setAiNote("");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  };

  const useDemo = () =>
    upload(new File([DEMO_BANK_CSV], "demo-bank-statement.csv", { type: "text/csv" }));

  const askAI = async () => {
    if (!preview) return;
    setBusy("ai");
    setError("");
    try {
      const result = await api<AIMappingResponse>(
        `/ingestion/${preview.upload_id}/ai-map`,
        { method: "POST" },
      );
      setMapping(
        Object.fromEntries(
          Object.entries(result.mapping).filter((entry): entry is [string, string] => Boolean(entry[1])),
        ),
      );
      setAiNote(`${result.generated_by}: ${result.warning}`);
      setConfirmed(false);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  };

  const commit = async () => {
    if (!preview || !confirmed) return;
    setBusy("commit");
    setError("");
    try {
      const result = await api<IngestionCommitResponse>("/ingestion/commit", {
        method: "POST",
        body: JSON.stringify({
          upload_id: preview.upload_id,
          field_mapping: mapping,
          amount_unit: unit,
        }),
      });
      setManifest(result.manifest);
      setPreview(null);
      setVerification(null);
      await loadManifests();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  };

  const verify = async (simulateTamper: boolean) => {
    if (!manifest) return;
    setBusy(simulateTamper ? "tamper" : "verify");
    setError("");
    try {
      const result = await api<IngestionVerification>(
        `/ingestion/manifests/${manifest.manifest_id}/verify`,
        { method: "POST", body: JSON.stringify({ simulate_tamper: simulateTamper }) },
      );
      setVerification(result);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  };

  const downloadManifest = () => {
    if (!manifest) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${manifest.manifest_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const requiredReady = preview?.required_fields.every((field) => mapping[field]);

  return (
    <div className="page intake-page">
      <PageHeader
        eyebrow="Cryptographic source boundary"
        title="Turn raw finance files into verifiable evidence."
        description="Preview and map untrusted CSVs, normalize money deterministically, then seal every accepted row inside an Ed25519-signed import manifest. Nothing enters the evidence layer silently."
      />

      <section className="trust-strip">
        <span><UploadCloud size={16} /> Untrusted CSV</span>
        <i>→</i>
        <span><Bot size={16} /> Header-only suggestion</span>
        <i>→</i>
        <span><ShieldCheck size={16} /> Human confirmation</span>
        <i>→</i>
        <span><FileKey2 size={16} /> Signed evidence</span>
      </section>

      {error && <div className="review-action-error"><XCircle size={16} />{error}</div>}

      {!preview && !manifest && (
        <section className="intake-start-grid">
          <article className="panel intake-config">
            <span className="panel-kicker">01 · Describe the source</span>
            <h2>Choose the financial system</h2>
            <p>ProofLedger applies a narrow schema and validation policy for each source.</p>
            <label className="field-label">
              Source type
              <select value={source} onChange={(event) => setSource(event.target.value as IngestionSource)}>
                {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </article>
          <article className="upload-zone">
            <UploadCloud size={30} />
            <strong>Drop in a UTF-8 CSV, TSV, or text export</strong>
            <p>Maximum 5 MB · 10,000 rows · staged for 30 minutes</p>
            <label className="primary-button file-button">
              {busy === "preview" ? "Inspecting…" : "Choose source file"}
              <input
                type="file"
                accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values"
                disabled={Boolean(busy)}
                onChange={(event) => event.target.files?.[0] && upload(event.target.files[0])}
              />
            </label>
            <button className="secondary-button" onClick={useDemo} disabled={Boolean(busy)}>
              <FlaskConical size={14} /> Run judge-ready demo file
            </button>
          </article>
        </section>
      )}

      {preview && (
        <>
          <section className="preview-summary">
            <div><span>Source file</span><strong>{preview.filename}</strong></div>
            <div><span>Rows staged</span><strong>{preview.row_count.toLocaleString("en-IN")}</strong></div>
            <div><span>SHA-256</span><code title={preview.file_sha256}>{shortHash(preview.file_sha256)}</code></div>
            <div><span>Expires</span><strong>{new Date(preview.expires_at).toLocaleTimeString("en-IN")}</strong></div>
          </section>

          <article className="panel mapping-panel">
            <div className="panel-heading">
              <div>
                <span className="panel-kicker">02 · Confirm schema</span>
                <h2>Every mapping stays controller-visible</h2>
              </div>
              <button className="secondary-button" onClick={askAI} disabled={Boolean(busy)}>
                <Bot size={14} /> {busy === "ai" ? "Suggesting…" : "Improve with bounded AI"}
              </button>
            </div>
            {aiNote && <div className="ai-boundary-note"><Bot size={15} /><span>{aiNote}</span></div>}
            <div className="mapping-grid mapping-head">
              <span>Canonical field</span><span>CSV column</span><span>Confidence</span>
            </div>
            {preview.suggestions.map((suggestion) => (
              <div className="mapping-grid" key={suggestion.canonical_field}>
                <div><strong>{suggestion.canonical_field.replaceAll("_", " ")}</strong>{suggestion.required && <em>required</em>}</div>
                <select
                  value={mapping[suggestion.canonical_field] ?? ""}
                  onChange={(event) => {
                    setMapping((current) => ({ ...current, [suggestion.canonical_field]: event.target.value }));
                    setConfirmed(false);
                  }}
                >
                  <option value="">Do not map</option>
                  {preview.headers.map((header) => <option key={header} value={header}>{header}</option>)}
                </select>
                <span className={`confidence ${suggestion.confidence >= .8 ? "high" : "low"}`}>
                  {Math.round(suggestion.confidence * 100)}% · {suggestion.method.replaceAll("_", " ")}
                </span>
              </div>
            ))}
            <div className="commit-bar">
              <label className="field-label amount-unit">
                Amounts expressed in
                <select value={unit} onChange={(event) => setUnit(event.target.value as "rupees" | "paise")}>
                  <option value="rupees">Rupees (₹)</option>
                  <option value="paise">Paise (integer)</option>
                </select>
              </label>
              <label className="controller-confirm">
                <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                I reviewed the mapping and authorize this immutable evidence import.
              </label>
              <button className="primary-button" onClick={commit} disabled={!requiredReady || !confirmed || Boolean(busy)}>
                <FileKey2 size={15} /> {busy === "commit" ? "Signing records…" : "Validate & sign import"}
              </button>
            </div>
          </article>

          <article className="table-panel sample-table">
            <div className="sample-title"><strong>Read-only row sample</strong><span>Values never go to Gemini</span></div>
            <table className="data-table"><thead><tr>{preview.headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
              <tbody>{preview.sample_rows.map((row, index) => <tr key={index}>{preview.headers.map((header) => <td key={header}>{row[header]}</td>)}</tr>)}</tbody>
            </table>
          </article>
        </>
      )}

      {manifest && (
        <section className="manifest-card">
          <div className="manifest-seal"><ShieldCheck size={30} /><span>Ed25519</span></div>
          <div className="manifest-copy">
            <span className="panel-kicker">03 · Evidence sealed</span>
            <h2>{manifest.record_count} records committed atomically</h2>
            <p>The manifest binds the original file hash, confirmed mapping, normalized record hashes, timestamp, and public verification key.</p>
            <div className="manifest-hashes">
              <div><span>Manifest hash</span><code title={manifest.manifest_hash}>{manifest.manifest_hash}</code></div>
              <div><span>Public key</span><code title={manifest.signing_public_key}>{manifest.signing_public_key}</code></div>
              <div><span>Signature</span><code title={manifest.signature}>{manifest.signature}</code></div>
            </div>
            <div className="certificate-actions">
              <button className="primary-button" onClick={() => verify(false)} disabled={Boolean(busy)}><ShieldCheck size={14} /> Verify evidence</button>
              <button className="danger-button" onClick={() => verify(true)} disabled={Boolean(busy)}><FlaskConical size={14} /> Simulate ₹1 tamper</button>
              <button className="secondary-button" onClick={downloadManifest}><Download size={14} /> Export manifest</button>
              <button className="text-button" onClick={() => { setManifest(null); setVerification(null); }}>Import another file</button>
            </div>
            {verification && (
              <div className={`verification ${verification.valid ? "valid" : "invalid"}`}>
                {verification.valid ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
                <div><strong>{verification.valid ? "Cryptographic chain intact" : "Mutation detected—evidence rejected"}</strong>
                  <small>{Object.entries(verification.checks).map(([name, passed]) => `${name.replaceAll("_", " ")}: ${passed ? "pass" : "fail"}`).join(" · ")}</small>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {manifests.length > 0 && (
        <article className="panel manifest-history">
          <span className="panel-kicker">Signed import history</span>
          {manifests.map((item) => (
            <button className="manifest-row" key={item.manifest_id} onClick={() => { setManifest(item); setPreview(null); setVerification(null); }}>
              <FileKey2 size={16} /><span><strong>{item.filename}</strong><small>{item.record_count} records · {SOURCE_LABELS[item.source_type]}</small></span><code>{shortHash(item.manifest_hash)}</code>
            </button>
          ))}
        </article>
      )}
    </div>
  );
}

export default DataIntakePage;
