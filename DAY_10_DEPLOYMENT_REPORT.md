# 1. Goal

Deploy the frozen MPLADS Sentinel prototype to public HTTPS endpoints, prove its existing officer-facing workflow end to end, and document operational limits without altering intelligence, source data, or governance.

# 2. Pre-Deployment State

The verified Day-9.2 checkpoint was `1492f5d756f2d549f5c321592beb795d6f800cc5` (`Complete Day 9.2 pre-deployment build`). The working branch was `main`, the private GitHub repository was `n240245-maker/SIH-PROJECT`, and the analytical snapshot remained `2026-09-01`. The annotated `day9.2-predeployment` rollback tag was created and pushed.

The repository contained the 3,000-work frozen artifacts, local MiniLM files, anomaly and predictive joblib models, guideline resources, Next.js frontend, FastAPI backend, and append-only JSONL review implementation. No database or Docker deployment was required.

# 3. Hosting Audit

The audit considered current free-tier suitability, private GitHub integration, build size, runtime model loading, HTTPS, environment variables, outbound HTTPS, filesystem behavior, and frontend framework support.

Render was selected for the backend because it supports a persistent Python web process, repository builds, health checks, secure server-side environment variables, outbound HTTPS, and the required 512 MB free-instance memory envelope. Its important tradeoffs are spin-down, cold-start delay, shared 0.1 CPU, and an ephemeral filesystem.

Vercel Hobby was selected for the frontend because it directly supports the existing Next.js 16 project, private GitHub deployments, HTTPS, production environment variables, and CDN delivery. The split avoids forcing the artifact-heavy FastAPI process into a small serverless function.

# 4. Selected Architecture

The frontend runs on Vercel and communicates over HTTPS with FastAPI on Render. FastAPI loads frozen artifacts read-only at application startup and lazily initializes heavier serving resources where appropriate. Local deterministic explanation and PDF generation remain available without Groq. The Groq API remains a server-side, explicit-action-only explanation provider.

# 5. Backend Deployment

Render service `mplads-sentinel-api` uses Python 3.12.10, build command `pip install --no-cache-dir -r requirements-deploy.txt`, start command `uvicorn backend.main:app --app-dir code --host 0.0.0.0 --port $PORT`, and health path `/health`. Deployment-specific work was limited to runtime dependencies, Linux-safe/writable runtime configuration, environment-configurable CORS, local offline-model resolution, startup memory control, and tests. No analytical formula, score, threshold, model, or frozen output was changed.

The latest verified application deployment process was `dep-daddpplg1s2s7384el8g`. After replacement, public health reported `ok`, `artifact_status=validated`, `work_count=3000`, and `as_of_date=2026-09-01`.

# 6. Frontend Deployment

Vercel deployed `code/frontend` as the Next.js application. `NEXT_PUBLIC_API_BASE_URL` points only to the public Render HTTPS API. Hosted Overview, Review Queue, filters, scoped views, work detail, evidence sections, trends, methodology, explanation controls, report download, and officer review submission rendered correctly.

# 7. Environment Variables

Render contains `PYTHON_VERSION`, `AS_OF_DATE`, `MPLADS_AS_OF_DATE`, `MPLADS_ENVIRONMENT`, `MPLADS_CORS_ORIGINS`, `MPLADS_RUNTIME_DATA_DIR`, `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `GROQ_MODEL`, `GROQ_BASE_URL`, `GROQ_TIMEOUT_SECONDS`, and the secret `GROQ_API_KEY`. Vercel contains only the public `NEXT_PUBLIC_API_BASE_URL` required by this deployment. No secret value is recorded in this report, source, provider configuration committed to Git, frontend build, or generated output.

# 8. CORS

The production allow-list is the exact Vercel origin `https://mplads-sentinel-one.vercel.app`. Both OPTIONS preflight and a normal GET returned that origin with HTTP 200. Wildcard CORS is not used.

# 9. Local Model / RAG Packaging

The committed `all-MiniLM-L6-v2` snapshot loads locally with Hugging Face and Transformers offline modes enabled. Normal operation therefore does not require an external model download. Frozen embeddings, guideline chunks, explanation context, and model artifacts were not regenerated. Retrieval remains local and bounded; the hosted provider receives only selected context after an explicit officer action.

# 10. Runtime Persistence

Review submission and its audit event successfully appended during the live instance. The configured location is `/tmp/mplads-sentinel-runtime`. A later restart reset the smoke record from one review to zero, empirically confirming Render Free's ephemeral filesystem. This is sufficient for an in-session prototype demonstration but is not durable production persistence.

# 11. Hosted API Verification

The following public API behavior passed:

- `/health`: HTTP 200, validated artifacts, 3,000 works.
- Metadata: policy `REVIEW_PRIORITY_POLICY_V0_1`, governed guideline identity, approved Groq model, deterministic default.
- Scope options: MOSPI, STATE, DISTRICT, and MP; missing required scope components returned HTTP 422, while valid state, district, and MP selections returned scoped data.
- Overview: 3,000 works, mean Review Priority `42.265258769666666`, and review queue count 1,104.
- Attention Levels: Normal 378; Low Attention 189; Medium Attention 1,329; High Attention 1,096; Immediate Priority 8.
- Requires Review: 2,470.
- `W-001937`: Review Priority `89.441901`, CRITICAL / Immediate Priority, duplicate review candidate with `W-001966`.
- `W-002760`: Review Priority `78.928155`, CRITICAL / Immediate Priority.
- `W-000933`: deterministic NON_COMPLIANT count 1.
- `W-000476`: Review Priority `1.191241`, LOW / Normal, `requires_review=false`.
- `W-000012`: Low Attention with actionable review evidence.
- `W-001437`: High Attention with small financial-exceedance presentation.
- `W-001966`: duplicate review candidate paired with `W-001937`.
- Work-detail family contributions reproduced each frozen Review Priority total.
- Bounded queue pagination, trends, hotspots, and alerts endpoints responded successfully.

# 12. Hosted Browser Verification

A clean hosted browser flow covered Overview, Review Queue, Attention and Requires Review filters, MOSPI and MP scope, the acceptance work details, compliance, duplicate review, peer comparison, forecast, AI Case Brief, trends/hotspots, methodology, PDF download, and officer review. The Normal record remained visually calm; high-attention records used governed, evidence-based warnings. No broken styling, missing icons, page-level desktop overflow, or application console error was observed. Primary prose used decision-support language rather than unsupported fraud or guilt claims.

# 13. Hosted PDF Verification

Reports for `W-001937` and `W-002760` returned HTTP 200 and `application/pdf`, had a valid `%PDF` signature, contained five pages and the correct work identifiers, included the prototype decision-support/review note, and contained no exact `NaN`, provider-key prefix, or stack trace. Report generation remained deterministic and made no Groq call.

# 14. Groq / Fallback Verification

All core application and report workflows passed first with the deterministic local fallback. Ordinary navigation did not contact Groq. After explicit user approval and secure server-side credential replacement, exactly one live hosted request was sent for `W-001937`; it returned `GROQ_GROUNDED`, `api_status=SUCCESS`, provider `groq`, approved model `openai/gpt-oss-120b`, seven retrieved guideline excerpts, and `fallback_used=false`. No retry was made.

# 15. Performance / Cold Start

Observed warm medians from three samples were approximately: health 275.9 ms, overview 232.6 ms, queue 258.1 ms, work detail 217.3 ms, and trends 479.1 ms. These are observations, not SLA commitments.

The initial Render deployment became usable in approximately 2 minutes 55 seconds. Render warns that a sleeping free service request may be delayed by 50 seconds or more. The demo procedure is to open `/health` two to three minutes before presentation and wait for the validated response.

# 16. Security / Secret Audit

The public frontend uses HTTPS and contains no Groq credential. `GROQ_API_KEY` is ignored locally and configured only as a Render server-side secret. Tracked-source, build/configuration, documentation, report, generated-summary, and Git-history checks found no active key value or authorization header.

During provider setup, an old Groq credential became visible to the browser-automation inspection output. It was immediately treated as compromised, revoked by the user, and replaced by the user directly in provider UIs. Codex did not read, print, or copy the replacement. The replacement is not present in the repository, frontend, reports, OpenAPI, or deployment documentation.

# 17. Data / Artifact Integrity

All 12 read-only Demo-data SHA-256 hashes matched their Day-0/Day-1 baselines. The Day-0 through Day-8.2 governed intelligence and model artifacts remained unchanged. The only generated Day-10 artifact is this non-secret deployment summary under `data/processed/application`. Ground truth remains evaluation-only and is not exposed to the application.

# 18. Free-Tier Limitations

The initial deployment remained free. Render Free can sleep, has shared 0.1 CPU and 512 MB RAM, provides ephemeral runtime files, and is subject to build/runtime quotas. Vercel Hobby has usage quotas. The deployment makes no uptime, performance, or durable-storage guarantee. No domain, paid plan, database, or add-on was purchased.

# 19. Public URLs

- Frontend: <https://mplads-sentinel-one.vercel.app>
- Backend: <https://mplads-sentinel-api.onrender.com>
- Health: <https://mplads-sentinel-api.onrender.com/health>

# 20. Rollback Instructions

The rollback checkpoint is tag `day9.2-predeployment` at commit `1492f5d756f2d549f5c321592beb795d6f800cc5`. Create a normal revert or deploy a branch created from that tag, then redeploy through Render and Vercel. Never force-push or rewrite `main` history.

# 21. Final Deployment Decision

**PASS.** Both public HTTPS applications work, the hosted API loads all 3,000 records with immutable scores and expected lifecycle presentation, role scope is enforced, the review queue and detail evidence work, PDFs are valid, deterministic explanation works offline, the one approved Groq request was grounded and successful, CORS is exact, and console/data/artifact/security checks passed. The known free-tier cold-start and ephemeral-review limitations are documented and do not invalidate the SIH prototype deployment.
