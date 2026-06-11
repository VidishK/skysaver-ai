# SkySaver AI — Cloud Run container
#
# What's inside:
#   • Python 3.12 slim base
#   • Node.js 22 — required so the MongoDB MCP server can spawn at runtime
#   • Python deps from requirements.txt
#   • The FastAPI app (api.py) served by uvicorn on $PORT
#
# At runtime, uvicorn listens on Cloud Run's injected $PORT (default 8080).
# The first chat request lazily spawns `npx mongodb-mcp-server` as a
# subprocess via mcp_bridge.py — pre-fetched below so cold start is fast.

FROM python:3.12-slim

# ---- System: Node.js 22 (for the MongoDB MCP server) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version \
    && npm --version

WORKDIR /app

# ---- Python dependencies ----
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- Pre-fetch the MongoDB MCP server into the npx cache ----
# Speeds up the first chat call by ~10s on cold start.
RUN npx --yes mongodb-mcp-server --help >/dev/null 2>&1 || true

# ---- Application code ----
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# Single worker keeps the MCP subprocess simple. Cloud Run scales by
# spawning more instances rather than more workers per instance.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
