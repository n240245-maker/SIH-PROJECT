# MPLADS Sentinel Deployment

## Architecture

The public prototype uses two managed free-tier services:

- Vercel hosts the Next.js frontend from `code/frontend`.
- Render hosts the persistent FastAPI web process from the repository root.
- The browser calls the Render API over HTTPS. The backend reads the committed, frozen analytical artifacts and keeps one-to-many evidence separate.
- GroqCloud is optional and is contacted only by the explicit explanation POST initiated by an officer. All ordinary navigation and report generation use local deterministic behavior.

Public endpoints:

- Frontend: <https://mplads-sentinel-one.vercel.app>
- Backend: <https://mplads-sentinel-api.onrender.com>
- Health: <https://mplads-sentinel-api.onrender.com/health>

No database or Docker image is used for this CSV-first prototype.

## Provider Configuration

### Render backend

- Service: `mplads-sentinel-api`
- Plan: Free
- Runtime: Python 3.12.10
- Region: Singapore
- Repository root: repository root
- Build command: `pip install --no-cache-dir -r requirements-deploy.txt`
- Start command: `uvicorn backend.main:app --app-dir code --host 0.0.0.0 --port $PORT`
- Health-check path: `/health`
- Blueprint: `render.yaml`

The runtime-only dependency set is in `requirements-deploy.txt`. It intentionally excludes training and development dependencies.

### Vercel frontend

- Plan: Hobby
- Framework: Next.js 16
- Root directory: `code/frontend`
- Install command: `npm ci`
- Build command: `npm run build`
- Public API setting: `NEXT_PUBLIC_API_BASE_URL=https://mplads-sentinel-api.onrender.com`

The Groq credential must never be configured in Vercel or in any `NEXT_PUBLIC_*` variable.

## Backend Environment Variables

The following names are configured on Render. The secret value is deliberately omitted.

| Variable | Purpose |
|---|---|
| `PYTHON_VERSION` | Pins Python 3.12.10. |
| `AS_OF_DATE` | Controls the frozen analytical snapshot date (`2026-09-01`). |
| `MPLADS_AS_OF_DATE` | Application-level snapshot date (`2026-09-01`). |
| `MPLADS_ENVIRONMENT` | Selects production configuration. |
| `MPLADS_CORS_ORIGINS` | Exact allowed Vercel origin. |
| `MPLADS_RUNTIME_DATA_DIR` | Writable append-only runtime directory (`/tmp/mplads-sentinel-runtime`). |
| `HF_HUB_OFFLINE` | Prevents unexpected Hugging Face downloads. |
| `TRANSFORMERS_OFFLINE` | Enforces offline transformer loading. |
| `GROQ_MODEL` | Pins `openai/gpt-oss-120b`. |
| `GROQ_BASE_URL` | GroqCloud OpenAI-compatible endpoint. |
| `GROQ_TIMEOUT_SECONDS` | Explicit-request timeout. |
| `GROQ_API_KEY` | Render secret; user-entered and server-side only. |

## CORS and HTTPS

Production CORS explicitly allows `https://mplads-sentinel-one.vercel.app`. Preflight and normal GET requests were verified to return that exact origin. The frontend API base and both public applications use HTTPS; unrestricted `*` CORS is not used.

## Local Model and RAG Packaging

The committed `sentence-transformers/all-MiniLM-L6-v2` cache is resolved locally. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` ensure judging does not depend on a model download. Frozen anomaly and predictive joblib artifacts remain in `code/models`; no model is trained or regenerated during build or startup.

The RAG corpus, guideline chunks, embeddings, and explanation context are committed frozen resources. Retrieval is local. Groq receives only the bounded, explicitly approved work context and retrieved guideline evidence when an officer clicks the generation action.

## Runtime Reviews and Audit Events

Officer reviews and matching audit events are appended to JSONL files in `/tmp/mplads-sentinel-runtime`. They work while the current Render instance is running, but Render Free provides an ephemeral filesystem. A restart, redeploy, or replacement instance can reset this demo state. This is not durable production persistence and must not be represented as such.

The verified restart reset a smoke-test review, confirming the limitation. A later production architecture will require an explicitly approved durable append-only store; no database migration is part of Day 10.

## Groq and Deterministic Fallback

Core detection, compliance, queue, detail, trends, and PDFs do not require Groq. The default explanation is deterministic and local. Groq is called only through `POST /api/v1/works/{work_id}/explain` with explicit user intent. Missing credentials, timeouts, rate limits, provider errors, invalid responses, or grounding failures return a safe fallback without exposing keys, prompts, payloads, or stack traces.

One approved hosted smoke request for `W-001937` succeeded with provider `groq`, model `openai/gpt-oss-120b`, generation mode `GROQ_GROUNDED`, seven retrieved guideline excerpts, and no fallback. It was not retried.

## PDF Reports

`GET /api/v1/works/{work_id}/case-report.pdf` generates reports server-side with ReportLab and does not require a desktop GUI or Poppler. Hosted reports for `W-001937` and `W-002760` returned HTTP 200, `application/pdf`, a valid `%PDF` signature, correct work identifiers, the decision-support note, and no secret, traceback, or `NaN` token. Downloading a report does not call Groq.

## Cold Start and Free-Tier Limits

Render Free spins the backend down after inactivity. Render states that a request to a sleeping service may be delayed by 50 seconds or more; the first deployment became usable in approximately 2 minutes 55 seconds. Before a demonstration, open the health URL two to three minutes early and wait for an `ok` response.

Other free-tier limitations include shared 0.1 CPU/512 MB backend resources, ephemeral runtime files, provider build/runtime quotas, and Vercel Hobby quotas. No uptime, latency, or durable-storage SLA is claimed. The application has no purchased domain or paid service.

## Operations

### Redeploy

1. Commit verified deployment-only changes to `main` and push normally to `origin/main`.
2. Render and Vercel are connected to the repository and deploy commits automatically.
3. Wait for both provider deployments to finish.
4. Check `/health`, then the hosted Overview, Review Queue, one detail page, and a PDF.

Never force-push, commit `.env`, or put `GROQ_API_KEY` in frontend settings.

### Wake before a demo

Open <https://mplads-sentinel-api.onrender.com/health> two to three minutes before presenting. Continue only after the response reports `status: ok`, `artifact_status: validated`, and `work_count: 3000`.

### Roll back

The stable pre-deployment checkpoint is commit `1492f5d756f2d549f5c321592beb795d6f800cc5`, tagged `day9.2-predeployment` and pushed to GitHub. Create a normal revert or a new branch/deployment from that tag; do not rewrite history or force-push. Provider dashboards can then redeploy the selected commit.

### Add a custom domain later

A future purchased domain can point its primary host to Vercel and `api.<domain>` to Render. Add and verify each domain in the relevant provider, change `NEXT_PUBLIC_API_BASE_URL`, and update the exact backend CORS origin. No domain was purchased or configured during Day 10.
