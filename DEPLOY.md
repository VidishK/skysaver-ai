# Deploying SkySaver AI to Google Cloud Run

This deploys the FastAPI app (`api.py`) + React frontend + MongoDB MCP
subprocess to a public HTTPS URL. End-to-end takes ~10 minutes.

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and logged in (`gcloud auth login`)
- A working local `.env` with `MONGO_URI` and `SERPAPI_KEY`
- A MongoDB Atlas cluster reachable from `0.0.0.0/0` (or Cloud Run's egress IPs)

## 1. One-time project setup

```bash
# Replace YOUR-PROJECT-ID with your GCP project id
gcloud config set project YOUR-PROJECT-ID
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com
```

## 2. Grant the Cloud Run service account Vertex AI access

Cloud Run uses the project's default compute service account. It needs to
call Vertex AI (for Gemini + Vision OCR):

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SA=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. Store secrets

```bash
gcloud secrets create MONGO_URI   --replication-policy="automatic" 2>/dev/null || true
gcloud secrets create SERPAPI_KEY --replication-policy="automatic" 2>/dev/null || true

# Pull values from your local .env (works on macOS/Linux)
gcloud secrets versions add MONGO_URI   --data-file=<(grep '^MONGO_URI='   .env | cut -d= -f2-)
gcloud secrets versions add SERPAPI_KEY --data-file=<(grep '^SERPAPI_KEY=' .env | cut -d= -f2-)
```

Sanity-check:

```bash
gcloud secrets versions access latest --secret=MONGO_URI   | head -c 40 ; echo
gcloud secrets versions access latest --secret=SERPAPI_KEY | head -c 12 ; echo
```

## 4. Deploy

```bash
gcloud run deploy skysaver-ai \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600 \
  --concurrency 80 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-secrets "MONGO_URI=MONGO_URI:latest,SERPAPI_KEY=SERPAPI_KEY:latest"
```

First deploy: ~5–7 minutes (Cloud Build builds the image and pre-fetches
the MongoDB MCP server). Re-deploys: ~2 minutes.

You'll get back a URL like:

```
Service URL: https://skysaver-ai-abc123-uc.a.run.app
```

## 5. Verify

```bash
# Server should respond (returns 401 unauth, which is correct)
curl -i https://skysaver-ai-abc123-uc.a.run.app/api/me
# → HTTP/2 401

# Open in browser, sign up, plan a trip, simulate disruption
open https://skysaver-ai-abc123-uc.a.run.app
```

Watch the live logs while you click through:

```bash
gcloud run services logs tail skysaver-ai --region $REGION
```

You should see:
- `Uvicorn running on http://0.0.0.0:8080`
- `[mcp_bridge] mongodb-mcp-server spawned` when you first send a chat
- No `BrokenResourceError` or `email-validator not installed` errors

## 6. Re-deploy after code changes

```bash
gcloud run deploy skysaver-ai --source . --region $REGION
```

Same command, ~2 minutes — Cloud Build only rebuilds changed layers.

## Common failures

| Symptom | Fix |
|---|---|
| `aiplatform: PERMISSION_DENIED` | Compute SA missing `roles/aiplatform.user` — see step 2 |
| `Cannot connect to MongoDB` | Atlas IP allowlist doesn't include `0.0.0.0/0` |
| `Failed to spawn npx` | Node didn't install — rebuild image |
| `Container failed to start` | Check `--port`; uvicorn must bind to `$PORT`, not 8000 |

## Cost

Cloud Run scales to zero. Idle = $0. A 5-minute judging visit costs under
$0.01. The $300 GCP free credit covers everything realistic.
