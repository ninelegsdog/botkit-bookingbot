FROM python:3.13-slim AS base
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --chown=botuser:botuser pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" && pip install --no-cache-dir .
COPY --chown=botuser:botuser . .
USER 1001:1001
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import aiohttp; print('ok')"
CMD ["python", "-m", "bot"]
