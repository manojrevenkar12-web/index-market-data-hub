# One image, two entrypoints: the API service (default) and the end-of-day job (python -m imdh.service.eod).
# Twelve-factor: every setting comes from the environment, logs go to stdout, the port comes from $PORT.
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 IMDH_STATIC_DIR=/app/web/dist
WORKDIR /app
COPY requirements.txt requirements-gcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-gcp.txt
COPY imdh/ imdh/
COPY config/ config/
COPY reports/ reports/
COPY --from=web /web/dist web/dist
RUN useradd --uid 10001 --no-create-home app
USER 10001
EXPOSE 8080
CMD ["python", "-m", "imdh.service"]
