# ──────────────────────────────────────────────────────────────
# gitstats3 — containerised build
# ──────────────────────────────────────────────────────────────
# Usage:
#   docker build -t gitstats3 .
#   docker run --rm \
#     -v /path/to/repo:/repo:ro \
#     -v /path/to/output:/output \
#     gitstats3 /repo /output
# ──────────────────────────────────────────────────────────────

# ── stage 1: install Python dependencies ─────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── stage 2: runtime image ───────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="Gitstats3 Contributors"
LABEL org.opencontainers.image.source="https://github.com/gitstats3/gitstats3"
LABEL org.opencontainers.image.description="Git repository statistics generator with OOP metrics analysis"

# git is the only system-level runtime dependency;
# gosu allows dropping privileges cleanly in the entrypoint
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Create a non-root user for default execution
RUN groupadd --gid 1000 gitstats \
    && useradd --uid 1000 --gid gitstats --create-home gitstats

# Copy application source
WORKDIR /app
COPY pyproject.toml .
COPY gitstats.py .
COPY src/ src/

# /repo  → mount the repository to analyse  (read-only is fine)
# /output → mount a host directory for generated reports
VOLUME ["/repo", "/output"]

# Entrypoint: ensure /output is writable, then drop to non-root
COPY <<'ENTRYPOINT' /usr/local/bin/docker-entrypoint.sh
#!/bin/sh
set -e
# Ensure the output directory is writable by the gitstats user
chown gitstats:gitstats /output 2>/dev/null || true
exec gosu gitstats python /app/gitstats.py "$@"
ENTRYPOINT
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["--help"]
