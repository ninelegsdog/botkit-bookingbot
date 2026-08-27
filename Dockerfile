FROM python:3.13-slim AS builder
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --chown=botuser:botuser pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" && pip install --no-cache-dir .

FROM python:3.13-slim AS runtime
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=botuser:botuser . .
USER 1001:1001
ARG PORT
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:${PORT}/health')"
CMD ["python", "-m", "bot"]