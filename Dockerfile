FROM python@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS builder
RUN useradd -m -u 1001 botuser
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# uv is used only to read uv.lock and emit a constraints file. It is deleted again
# before the layer is sealed, and the runtime stages copy site-packages only, so the
# binary never reaches the shipped image.
COPY --from=ghcr.io/astral-sh/uv@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
COPY --chown=botuser:botuser pyproject.toml uv.lock .
RUN --mount=type=secret,id=BOTKIT_CORE_TOKEN bash <<'EOF'
    set -e
    if [ -f /run/secrets/BOTKIT_CORE_TOKEN ]; then
      git config --global url."https://x-access-token:$(cat /run/secrets/BOTKIT_CORE_TOKEN)@github.com/ninelegsdog/botkit-core".insteadOf "https://github.com/ninelegsdog/botkit-core"
    fi
    # Exact versions from uv.lock. `pip install .` alone resolved `>=` ranges against
    # whatever the index held at build time, so two builds of one revision could differ
    # and a rebuild months later would pick up versions nobody reviewed. `--locked` fails
    # the build if pyproject.toml and uv.lock disagree.
    uv export --locked --no-emit-project --no-hashes --all-extras -o /tmp/constraints.txt
    pip install --no-cache-dir -c /tmp/constraints.txt -e ".[dev]" && pip install --no-cache-dir -c /tmp/constraints.txt .
    rm -f ~/.gitconfig /tmp/constraints.txt /usr/local/bin/uv
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
ARG BUILD_SHA
ENV BUILD_SHA=$BUILD_SHA
CMD ["python", "-m", "bot"]
