FROM python:3.12-slim-bookworm

ARG PATCHRIGHT_VERSION=1.62.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    XDG_CACHE_HOME=/cache

WORKDIR /app

# Install drivers and browsers during the build, not at startup.
# Camoufox (anti-detect Firefox) is the default solver browser; its binary and
# fingerprint model are fetched here too so the image is self-contained.
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt "patchright==${PATCHRIGHT_VERSION}" \
    && python -m patchright install --with-deps --no-shell chromium \
    && python -m camoufox fetch \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 solver \
    && useradd --uid 10001 --gid solver --create-home solver \
    && chown -R solver:solver /cache

COPY api.py ./
COPY core/ ./core/
COPY turnstile/ ./turnstile/
COPY cf_clearance/ ./cf_clearance/
# Credentials stay outside the image; mount a proxy file here when needed.
RUN touch /app/proxies.txt && chmod 644 /app/proxies.txt

USER solver

LABEL org.opencontainers.image.source="https://github.com/zeroornull/Turnstile-Solver-NEW" \
      org.opencontainers.image.url="https://github.com/zeroornull/Turnstile-Solver-NEW" \
      org.opencontainers.image.description="Cloudflare Turnstile and IUAM solver API with bundled Camoufox and Chromium"

EXPOSE 5072

ENTRYPOINT ["python", "api.py", "--browser_type", "camoufox"]
