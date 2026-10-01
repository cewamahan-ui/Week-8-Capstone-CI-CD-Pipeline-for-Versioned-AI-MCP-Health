# AfyaPlus triage - Week 8 capstone image.
# Same slim-base, non-root, cache-friendly habits as Weeks 6-7. Week 8
# adds build ARGs so image tags carry the release identity, and bakes
# the prompt bundle + config into the image so the pin is verifiable
# at runtime via /health.

FROM python:3.12-slim

# Build identity - passed by CI so the tag, git SHA and versions agree.
ARG APP_VERSION=1.3.0-candidate
ARG BUILD_SHA=dev
ARG RELEASE_TAG=v1.3.0-candidate
ENV APP_VERSION=${APP_VERSION} \
    BUILD_SHA=${BUILD_SHA} \
    RELEASE_TAG=${RELEASE_TAG}

RUN groupadd --system appuser && useradd --system --gid appuser appuser

WORKDIR /app

# 1) Deps layer - rebuilds only when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Versioned artefacts layer - prompts, config, clinic data.
COPY prompts/ ./prompts/
COPY config/ ./config/
COPY clinics.json ./

# 3) Code layer.
COPY versions.py prompt_loader.py prompt_app.py triage_stub.py check_prompt_pin.py ./
COPY logistics_mcp_versioned.py ./

# Fail the build if the pin does not match - a broken bundle never ships.
RUN python check_prompt_pin.py

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"

# PROMPT_VERSION chooses the bundle at runtime (default: config pin).
# Rollback = redeploy the previous tag or set PROMPT_VERSION=1.2.0.
ENTRYPOINT ["python", "-m", "uvicorn", "prompt_app:app", \
            "--host", "0.0.0.0", "--port", "8000"]
