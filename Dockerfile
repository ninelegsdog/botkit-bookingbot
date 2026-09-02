FROM python@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS builder
RUN useradd -m -u 1001 botuser
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --chown=botuser:botuser pyproject.toml .
RUN --mount=type=secret,id=BOTKIT_CORE_TOKEN bash <<'EOF'
    set -e
    if [ -f /run/secrets/BOTKIT_CORE_TOKEN ]; then
      git config --global url."https://x-access-token:$(cat /run/secrets/BOTKIT_CORE_TOKEN)@github.com/ninelegsdog/botkit-core".insteadOf "https://github.com/ninelegsdog/botkit-core"
    fi
    pip install --no-cache-dir -e ".[dev]" && pip install --no-cache-dir .
    rm -f ~/.gitconfig
    apt-get purge -y --auto-remove git
    rm -rf /var/lib/apt/lists/*
EOF

FROM python@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS runtime
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=botuser:botuser . .
USER 1001:1001
ARG PORT
CMD ["python", "-m", "bot"]
