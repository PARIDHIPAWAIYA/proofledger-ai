# Deployment

Two services: the FastAPI backend on Render, the React console on Vercel. Neither needs a Gemini
key — the deterministic fallback keeps every feature working.

Both steps require signing in through a browser, so run them from your own machine.

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

## 2. Frontend on Vercel

1. Sign in at https://vercel.com with GitHub and import the same repository.
2. Set **Root Directory** to `apps/web`. This is the one setting that is easy to miss; without it
   the build cannot find `package.json`.
3. Framework preset resolves to Vite from `apps/web/vercel.json`. Leave the build command and
   output directory alone.
4. Add one environment variable:

   | Name | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://<your-service>.onrender.com/api/v1` |

   Vite inlines this at build time, so changing it later requires a redeploy.
5. Deploy, then record the frontend URL.

## 3. Close the CORS loop

Back in Render → `proofledger-api` → **Environment**, set:

| Name | Value |
| --- | --- |
| `PROOFLEDGER_CORS_ORIGINS` | your Vercel URL, no trailing slash |

Add `PROOFLEDGER_DATABASE_URL` here too if you attach managed PostgreSQL. Save and let the
service restart, then reload the frontend. The dashboard should populate.

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

## Local container

~~~powershell
docker build -t proofledger-ai:local .
docker run --rm -p 8000:8000 `
  -e PROOFLEDGER_DATABASE_URL=sqlite:////data/proofledger.db `
  -v proofledger-data:/data proofledger-ai:local
~~~
