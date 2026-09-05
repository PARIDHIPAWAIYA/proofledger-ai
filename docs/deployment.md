# Deployment

Two pieces:

- **Console** — static build, deployed to GitHub Pages by `.github/workflows/pages.yml`.
  Already live at https://paridhipawaiya.github.io/proofledger-ai/ and needs no third-party
  account. Vercel remains a supported alternative and is documented at the end.
- **Backend** — FastAPI, needs a persistent process, deployed to Render from `render.yaml`.

Neither needs a Gemini key; the deterministic fallback keeps every feature working.

## Why the backend cannot be serverless

The API keeps state in the running process, not only in the database: staged CSV previews between
preview and commit, the per-process Ed25519 manifest signing key, issued certificates, and review
resolutions. A serverless platform can route consecutive requests to different instances, which
would break upload → map → sign → verify → activate in ways that look like random failure. Deploy
it as one long-lived container.

## 1. Backend on Render

1. Sign in at https://dashboard.render.com with GitHub.
2. **New → Blueprint**, pick `PARIDHIPAWAIYA/proofledger-ai`. Render reads `render.yaml` and
   proposes a Docker web service named `proofledger-api` with a `/health` check.
3. Leave the three `sync: false` variables blank for now and deploy. The first build takes a few
   minutes.
4. Confirm the service is live:

~~~
https://<your-service>.onrender.com/health          → {"status":"ok","version":"0.1.0"}
https://<your-service>.onrender.com/api/v1/overview → close metrics
https://<your-service>.onrender.com/docs            → OpenAPI console
~~~

Record the base URL. You come back in step 3 to set CORS.

## 2. Point the console at it

`VITE_API_BASE_URL` is inlined into the bundle at build time, so it lives in a repository variable
and takes effect on the next Pages build:

~~~powershell
gh variable set VITE_API_BASE_URL --repo <owner>/proofledger-ai `
  --body "https://<your-service>.onrender.com/api/v1"
gh workflow run pages.yml --repo <owner>/proofledger-ai
~~~

Or set it under **Settings → Secrets and variables → Actions → Variables** and re-run the
"Operator console on GitHub Pages" workflow.

## 3. Close the CORS loop

Back in Render → `proofledger-api` → **Environment**, set:

| Name | Value |
| --- | --- |
| `PROOFLEDGER_CORS_ORIGINS` | `https://<owner>.github.io`, no trailing slash and no path |

A browser sends only the scheme and host as the `Origin` header, so the Pages project sub-path is
not part of this value.

Add `PROOFLEDGER_DATABASE_URL` here too if you attach managed PostgreSQL. Save and let the
service restart, then reload the console. The dashboard should populate.

## 4. Optional: bounded Gemini

Set `PROOFLEDGER_GEMINI_API_KEY` on Render only. It must never reach the browser bundle. Without
it, schema mapping and control explanations fall back to deterministic output and every other
feature is unchanged.

## Free-tier behaviour to know before recording a demo

- **Cold starts.** A free Render service sleeps after inactivity and takes 30–60 seconds to wake.
  Load `/health` a minute before recording.
- **Ephemeral signing key.** The Ed25519 manifest key is generated per process. A service restart
  invalidates signatures created before it, so complete an upload → verify → activate sequence
  inside one session rather than across a restart.
- **Ephemeral database.** The default SQLite file lives on the container filesystem and resets on
  redeploy. Attach managed PostgreSQL through `PROOFLEDGER_DATABASE_URL` if imports must survive.
- **Deterministic base workspace.** The built-in synthetic close regenerates identically on every
  boot, so a restart always returns the demo to a known state.

## Verify the deployment

~~~powershell
curl https://<your-service>.onrender.com/health
curl https://<your-service>.onrender.com/api/v1/overview
curl https://<your-service>.onrender.com/api/v1/benchmark
curl https://<your-service>.onrender.com/api/v1/calibration
~~~

Then open the Vercel URL and walk the demo script end to end: intake → sign → tamper → activate →
review → certificate → benchmark.

## Alternative: console on Vercel

`apps/web/vercel.json` is kept for this. Import the repository at https://vercel.com, set **Root
Directory** to `apps/web` — the one setting that is easy to miss, and without it the build cannot
find `package.json` — and add `VITE_API_BASE_URL` as a project environment variable. Then set
`PROOFLEDGER_CORS_ORIGINS` on Render to the Vercel origin instead of the Pages one.

## Local container

~~~powershell
docker build -t proofledger-ai:local .
docker run --rm -p 8000:8000 `
  -e PROOFLEDGER_DATABASE_URL=sqlite:////data/proofledger.db `
  -v proofledger-data:/data proofledger-ai:local
~~~
