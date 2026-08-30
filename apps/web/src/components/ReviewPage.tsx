import {
  BrainCircuit,
  CheckCircle2,
  FileQuestion,
  Fingerprint,
  Link2,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, formatMoney, formatPercent } from "../api";
import { evidenceFingerprint } from "../reviewEvidence";
import type {
  Review,
  ReviewResolution,
  ReviewResolutionOutcome,
} from "../types";
import { ErrorState, LoadingState, PageHeader, StatusBadge } from "./Shared";

type ReviewDraft = {
  candidateId: string;
  bankReference: string;
};

function ReviewPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [history, setHistory] = useState<ReviewResolution[]>([]);
  const [drafts, setDrafts] = useState<Record<string, ReviewDraft>>({});
  const [result, setResult] = useState<ReviewResolutionOutcome | null>(null);
  const [submitting, setSubmitting] = useState("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const loadWorkspace = useCallback(async () => {
    const [nextReviews, nextHistory] = await Promise.all([
      api<Review[]>("/reviews"),
      api<ReviewResolution[]>("/reviews/history"),
    ]);
    setReviews(nextReviews);
    setHistory(nextHistory);
    setDrafts((current) => {
      const next = { ...current };
      nextReviews.forEach((review) => {
        next[review.question.question_id] ??= {
          candidateId: "",
          bankReference: review.expected_bank_reference ?? "",
        };
      });
      return next;
    });
    setLoaded(true);
  }, []);

  useEffect(() => {
    loadWorkspace().catch((reason: Error) => {
      setError(reason.message);
      setLoaded(true);
    });
  }, [loadWorkspace]);

  const updateDraft = (questionId: string, update: Partial<ReviewDraft>) => {
    setDrafts((current) => {
      const existing = current[questionId] ?? {
        candidateId: "",
        bankReference: "",
      };
      return {
        ...current,
        [questionId]: { ...existing, ...update },
      };
    });
  };

  const resolve = async (review: Review) => {
    const settlement = review.settlement;
    if (!settlement) return;
    const questionId = review.question.question_id;
    const draft = drafts[questionId] ?? {
      candidateId: "",
      bankReference: review.expected_bank_reference ?? "",
    };
    const postedAt = new Date(settlement.occurred_at);
    postedAt.setUTCDate(postedAt.getUTCDate() + 1);
    const externalId = `statement_${settlement.settlement_id}_${questionId.slice(-6)}`;
    const fingerprint = await evidenceFingerprint({
      question_id: questionId,
      candidate_id: draft.candidateId || null,
      bank_reference: draft.bankReference,
      amount_paise: settlement.net_paise,
      occurred_at: postedAt.toISOString(),
      external_id: externalId,
      source: "synthetic_july_2026_bank_statement",
    });

    setSubmitting(questionId);
    setActionError("");
    try {
      const outcome = await api<ReviewResolutionOutcome>(
        `/reviews/${questionId}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({
            candidate_id: draft.candidateId || null,
            bank_reference: draft.bankReference,
            amount_paise: settlement.net_paise,
            occurred_at: postedAt.toISOString(),
            external_id: externalId,
            evidence_sha256: fingerprint,
            actor: "PARIDHIPAWAIYA (demo controller)",
            rationale:
              "Verified payout UTR and amount against the attached synthetic July 2026 bank statement row.",
          }),
        },
      );
      setResult(outcome);
      await loadWorkspace();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Review failed");
    } finally {
      setSubmitting("");
    }
  };

  if (error) return <ErrorState message={error} />;
  if (!loaded) return <LoadingState />;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Minimum-evidence review"
        title="Ask one question. Recompute the close."
        description="A controller attaches the smallest missing proof. ProofLedger hashes the action, enriches the evidence graph, and reruns every deterministic control—without rewriting the source row."
      />

      {result && (
        <section className="resolution-result">
          <div className="resolution-icon"><CheckCircle2 size={22} /></div>
          <div className="resolution-copy">
            <span className="panel-kicker">Authoritative recomputation complete</span>
            <h2>
              Review queue {result.queue_before} → {result.queue_after}
            </h2>
            <p>
              {result.affected_settlements.map((item) => (
                <span key={item.settlement_id}>
                  <strong>{item.settlement_id}</strong>: {item.before_status} → {item.after_status}.{" "}
                </span>
              ))}
              {result.remaining_blockers.length
                ? `Still blocked by ${result.remaining_blockers.join(", ")}.`
                : "No deterministic blockers remain for this payout."}
            </p>
          </div>
          <div className="audit-proof">
            <Fingerprint size={16} />
            <div>
              <span>Audit hash verified</span>
              <code>{result.resolution.resolution_hash.slice(0, 16)}…</code>
            </div>
          </div>
        </section>
      )}

      {actionError && (
        <div className="review-action-error">
          <LockKeyhole size={17} /> {actionError}
        </div>
      )}

      <div className="review-principle">
        <BrainCircuit size={22} />
        <div>
          <strong>AI chooses the wording—not the financial answer.</strong>
          <p>
            Controller evidence can add a missing fact. It cannot override amount controls,
            mutate the source, or rubber-stamp a close.
          </p>
        </div>
        <span>{reviews.length} open</span>
      </div>

      {reviews.length === 0 ? (
        <section className="empty-review-state panel">
          <ShieldCheck size={28} />
          <h2>Every evidence question is resolved.</h2>
          <p>The close still depends on all deterministic controls and maker-checker approval.</p>
        </section>
      ) : (
        <section className="review-grid">
          {reviews.map((review, index) => {
            const { question, decision, settlement } = review;
            const draft = drafts[question.question_id] ?? {
              candidateId: "",
              bankReference: review.expected_bank_reference ?? "",
            };
            const exactMismatch =
              decision.right_record_ids.length > 0 && decision.candidates.length === 0;
            const isSubmitting = submitting === question.question_id;

            return (
              <article className="review-card" key={question.question_id}>
                <div className="review-rank">{String(index + 1).padStart(2, "0")}</div>
                <div className="review-body">
                  <div className="review-meta">
                    <StatusBadge status={decision.status} />
                    <span>
                      Information gain {formatPercent(question.expected_information_gain)}
                    </span>
                    {settlement && <span>{settlement.settlement_id}</span>}
                  </div>
                  <h2>{question.prompt}</h2>
                  <div className="request-chip">
                    <FileQuestion size={15} />
                    Requested: {question.evidence_requested}
                  </div>

                  {exactMismatch ? (
                    <div className="control-lock">
                      <LockKeyhole size={19} />
                      <div>
                        <strong>Evidence cannot override this mismatch.</strong>
                        <p>
                          An exact bank row is already linked. Correct the source adjustment;
                          attaching a duplicate row is rejected by the API.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="evidence-workbench">
                      <div className="workbench-heading">
                        <div>
                          <span className="panel-kicker">Evidence attachment</span>
                          <strong>Verify a statement row</strong>
                        </div>
                        <span>{settlement ? formatMoney(settlement.net_paise) : "—"}</span>
                      </div>

                      <label
                        className={`evidence-option ${
                          draft.candidateId === "" ? "selected" : ""
                        }`}
                      >
                        <input
                          type="radio"
                          name={`candidate-${question.question_id}`}
                          checked={draft.candidateId === ""}
                          onChange={() => updateDraft(question.question_id, { candidateId: "" })}
                        />
                        <UploadCloud size={17} />
                        <span>
                          <strong>Attach new statement row</strong>
                          <small>Best when no safe candidate contains the payout UTR.</small>
                        </span>
                      </label>

                      {decision.candidates.length > 0 && (
                        <div className="candidate-list selectable-candidates">
                          <div className="candidate-head">
                            <span>Ranked candidate</span>
                            <span>Amount delta</span>
                            <span>Confidence</span>
                          </div>
                          {decision.candidates.slice(0, 3).map((candidate) => (
                            <label
                              className={`candidate-row ${
                                draft.candidateId === candidate.candidate_id ? "selected" : ""
                              }`}
                              key={candidate.candidate_id}
                            >
                              <span className="candidate-identity">
                                <input
                                  type="radio"
                                  name={`candidate-${question.question_id}`}
                                  checked={draft.candidateId === candidate.candidate_id}
                                  onChange={() =>
                                    updateDraft(question.question_id, {
                                      candidateId: candidate.candidate_id,
                                    })
                                  }
                                />
                                <strong>{candidate.candidate_id}</strong>
                              </span>
                              <span>{formatMoney(candidate.amount_delta_paise)}</span>
                              <span>{formatPercent(candidate.confidence)}</span>
                            </label>
                          ))}
                        </div>
                      )}

                      <label className="utr-field">
                        <span>Verified bank UTR</span>
                        <div>
                          <Link2 size={16} />
                          <input
                            value={draft.bankReference}
                            onChange={(event) =>
                              updateDraft(question.question_id, {
                                bankReference: event.target.value.toUpperCase(),
                              })
                            }
                            placeholder="Enter the UTR from the statement"
                          />
                        </div>
                      </label>

                      <div className="evidence-disclosure">
                        <Fingerprint size={15} />
                        The demo hashes this synthetic attachment before submission. The API
                        preserves the original bank row and records a separate controller action.
                      </div>
                      <button
                        className="primary-button"
                        disabled={isSubmitting || !draft.bankReference}
                        onClick={() => void resolve(review)}
                      >
                        {isSubmitting ? (
                          <><RefreshCw className="spin" size={15} /> Re-running controls</>
                        ) : (
                          <><ShieldCheck size={15} /> Attach proof &amp; recompute</>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </section>
      )}

      {history.length > 0 && (
        <section className="review-history panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Append-only controller trail</span>
              <h2>Verified review actions</h2>
            </div>
            <Fingerprint size={20} />
          </div>
          {history.slice(0, 5).map((entry) => (
            <div className="history-row" key={entry.resolution_id}>
              <CheckCircle2 size={16} />
              <div>
                <strong>{entry.provided_bank_reference}</strong>
                <small>{entry.actor} · {new Date(entry.resolved_at).toLocaleString("en-IN")}</small>
              </div>
              <code>{entry.resolution_hash.slice(0, 14)}…</code>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

export default ReviewPage;
