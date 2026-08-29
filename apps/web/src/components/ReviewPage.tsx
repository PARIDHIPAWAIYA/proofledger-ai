import {
  ArrowUpRight,
  BrainCircuit,
  Check,
  FileQuestion,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, formatMoney, formatPercent } from "../api";
import type { Review } from "../types";
import { ErrorState, LoadingState, PageHeader, StatusBadge } from "./Shared";

function ReviewPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [resolved, setResolved] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  useEffect(() => {
    api<Review[]>("/reviews")
      .then(setReviews)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!reviews.length) return <LoadingState />;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Minimum-evidence review"
        title="Ask one question. Resolve the graph."
        description="The queue is ranked by expected information gain. ProofLedger requests the smallest missing evidence that can separate plausible financial matches."
      />

      <div className="review-principle">
        <BrainCircuit size={22} />
        <div>
          <strong>AI chooses the wording—not the financial answer.</strong>
          <p>Candidate scores come from measurable amount, date, and reference evidence. A controller supplies the missing proof.</p>
        </div>
        <span>{reviews.length - resolved.size} open</span>
      </div>

      <section className="review-grid">
        {reviews.map(({ question, decision }, index) => {
          const isResolved = resolved.has(question.question_id);
          return (
            <article
              className={"review-card " + (isResolved ? "resolved" : "")}
              key={question.question_id}
            >
              <div className="review-rank">{String(index + 1).padStart(2, "0")}</div>
              <div className="review-body">
                <div className="review-meta">
                  <StatusBadge status={decision.status} />
                  <span>Information gain {formatPercent(question.expected_information_gain)}</span>
                </div>
                <h2>{question.prompt}</h2>
                <div className="request-chip">
                  <FileQuestion size={15} />
                  Requested: {question.evidence_requested}
                </div>

                {decision.candidates.length > 0 && (
                  <div className="candidate-list">
                    <div className="candidate-head">
                      <span>Candidate bank row</span>
                      <span>Amount delta</span>
                      <span>Confidence</span>
                    </div>
                    {decision.candidates.slice(0, 3).map((candidate) => (
                      <div className="candidate-row" key={candidate.candidate_id}>
                        <strong>{candidate.candidate_id}</strong>
                        <span>{formatMoney(candidate.amount_delta_paise)}</span>
                        <span>{formatPercent(candidate.confidence)}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="review-actions">
                  <button className="secondary-button">
                    Attach evidence <ArrowUpRight size={15} />
                  </button>
                  <button
                    className="text-button"
                    onClick={() =>
                      setResolved((current) => {
                        const next = new Set(current);
                        next.add(question.question_id);
                        return next;
                      })
                    }
                  >
                    <Check size={15} /> Mark demo reviewed
                  </button>
                </div>
              </div>
              {isResolved && (
                <div className="resolved-stamp">
                  <ShieldCheck size={18} />
                  Demo reviewed
                </div>
              )}
            </article>
          );
        })}
      </section>
    </div>
  );
}

export default ReviewPage;
