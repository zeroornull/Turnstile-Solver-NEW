FROM python:3.12-slim-bookworm

ARG PATCHRIGHT_VERSION=1.62.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install the driver and its matching full Chromium during the build, not startup.
# The app uses channel="chromium" with --headless=new, so no headless shell is needed.
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt "patchright==${PATCHRIGHT_VERSION}" \
    && python -m patchright install --with-deps --no-shell chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 solver \
    && useradd --uid 10001 --gid solver --create-home solver

COPY api.py ./
COPY core/ ./core/
COPY turnstile/ ./turnstile/
COPY cf_clearance/ ./cf_clearance/
# Credentials stay outside the image; mount a proxy file here when needed.
RUN touch /app/proxies.txt && chmod 644 /app/proxies.txt

USER solver

LABEL org.opencontainers.image.source="https://github.com/zeroornull/Turnstile-Solver-NEW"

EXPOSE 5072

ENTRYPOINT ["python", "api.py", "--browser_type", "chromium"]
