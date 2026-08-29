# ProofLedger AI

> Object-centric, uncertainty-aware financial close controller for Razorpay merchants.

ProofLedger reconstructs how merchant orders become captured payments, refunds, settlements,
bank credits, and accounting entries. It combines deterministic finance controls, calibrated
matching, minimum-evidence human review, bounded Gemini explanations, and independently
verifiable close certificates.

The product thesis is simple: **finance teams need proof, not a confident-looking match.**

## What makes it different

Generic reconciliation tools flatten rows and return a match score. ProofLedger instead:

1. Reconstructs an object/event graph across five financial sources.
2. Applies exact and composite evidence before any probabilistic assistance.
3. Abstains when candidate evidence is unsafe or ambiguous.
4. Asks the smallest question likely to resolve that uncertainty.
5. Enforces ten deterministic accounting and lifecycle controls.
6. Proposes a balanced journal that remains pending human approval.
7. Issues a proof-carrying settlement certificate only when critical controls pass.
8. Detects if any certified source evidence changes—even by ₹1.
9. Benchmarks safety using incorrect automatic approvals, not only aggregate accuracy.

## Demo result

The deterministic seed creates more than 1,200 records across merchant orders,
Razorpay-shaped reconciliation, refunds, bank statements, and a general ledger. It injects
missing bank evidence, a ₹1 amount difference, absent references, and a duplicate journal.

On the included held-out scenario:

| Method | Precision | Recall | F1 | Human review | Wrong auto-approvals |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact ID baseline | 100% | 40% | 57.1% | 0% | 0 |
| Fuzzy narration baseline | 50% | 60% | 54.6% | 0% | 3 |
| **ProofLedger** | **100%** | **100%** | **100%** | **33.3%** | **0** |

These numbers are from synthetic data and are not presented as production performance.
The committed benchmark exposes its labels, methods, and caveats for inspection.

## Product tour

- **Close command:** captured volume, close readiness, exception runway, and proof graph counts.
- **Settlement book:** payout-by-payout evidence, controls, and balanced journal proposals.
- **Evidence review:** questions ranked by expected information gain.
- **Lifecycle graph:** interactive order → payment → settlement → bank → ledger traversal.
- **Safety benchmark:** exact, fuzzy, and ProofLedger outcomes side by side.
- **Certificate lab:** issue a valid close certificate, change one source by ₹1, and watch
  verification fail.

## AI boundary

Gemini is optional. When configured, it may:

- explain a deterministic control result in plain language;
- phrase the next evidence question;
- assist a future schema-mapping workflow.

Gemini cannot accept a match, pass a control, approve a journal, alter a source record, or close
a settlement. Without an API key, the same application works with a deterministic explanation
fallback.

## Architecture

~~~text
Five source systems
  └─> immutable, SHA-256-hashed evidence records
       └─> object-centric lifecycle graph
            ├─> exact / composite reconciliation
            ├─> calibrated candidate sets + safe abstention
            ├─> ten deterministic finance controls
            └─> minimum-evidence controller review
                   ├─> balanced journal proposal
                   └─> verifiable settlement certificate
~~~

Authoritative money calculations use integer paise. Probabilistic output never enters an
accounting equation.

## Repository map

~~~text
apps/
  api/proofledger/
    domain/       immutable models, graph, controls, reconciliation, calibration
    services/     synthetic data, benchmark, bounded AI, closing, demo workspace
    api.py        FastAPI product endpoints
    main.py       application entrypoint
  web/
    src/          React operator console
docs/             architecture, controls, evaluation, demo, threat model
tests/            finance engine, certificate, benchmark, and API tests
.github/workflows continuous integration
~~~

## Run locally

Requirements:

- Python 3.10 or newer
- Node.js 22 or newer

Backend:

~~~powershell
python -m pip install -e ".[dev]"
python -m uvicorn proofledger.main:app --reload
~~~

Frontend, in a second terminal:

~~~powershell
cd apps/web
npm install
npm run dev
~~~

Open http://localhost:5173. FastAPI documentation is available at
http://localhost:8000/docs.

The demo does not require Gemini. To enable bounded explanations, copy .env.example to .env
and set PROOFLEDGER_GEMINI_API_KEY.

Reproduce a workspace or benchmark directly:

~~~powershell
proofledger summary
proofledger --seed 11 --orders 120 --settlement-size 20 benchmark
~~~

## Verify the repository

~~~powershell
python -m ruff check .
python -m pytest --cov=proofledger --cov-report=term-missing

cd apps/web
npm audit --omit=dev
npm run lint
npm run test
npm run build
~~~

## API surface

| Endpoint | Purpose |
| --- | --- |
| GET /health | Runtime health |
| GET /api/v1/overview | Close metrics and graph summary |
| GET /api/v1/settlements | Settlement control book |
| GET /api/v1/settlements/{id} | Evidence, controls, decision, and journal |
| GET /api/v1/reviews | Minimum-evidence review queue |
| GET /api/v1/benchmark | Held-out baseline comparison |
| GET /api/v1/graph/{id} | Lifecycle graph for one settlement |
| POST /api/v1/settlements/{id}/certificate | Issue certificate or return a blocking control |
| POST /api/v1/certificates/{id}/verify | Verify evidence; optionally simulate ₹1 tampering |
| POST /api/v1/controls/{id}/explain | Bounded Gemini or deterministic explanation |

## Deployment

- Backend: Dockerfile and render.yaml are included for Render.
- Frontend: deploy apps/web to Vercel and set VITE_API_BASE_URL to the deployed API URL
  followed by /api/v1.
- Backend CORS: set PROOFLEDGER_CORS_ORIGINS to the final frontend origin.
- Gemini: PROOFLEDGER_GEMINI_API_KEY is optional and must remain server-side.

## Honest scope

This project uses deterministic synthetic data inspired by public payment entity shapes. It does
not claim access to Razorpay production data, move money, execute refunds, post a real journal, or
provide tax/legal advice. Real deployment requires connector authentication, authorization,
retention controls, maker-checker approval, observability, and validation on merchant-specific
historical data.

See docs/limitations.md and docs/threat-model.md before treating this as production software.

## Documentation

- docs/architecture.md — system boundaries and data flow
- docs/control-catalog.md — all ten authoritative controls
- docs/evaluation.md — benchmark protocol and caveats
- docs/demo-script.md — six-minute judge walkthrough
- docs/threat-model.md — abuse cases and mitigations
- docs/decisions.md — architecture decision records

## Author

**PARIDHIPAWAIYA**

Released under the MIT License.
