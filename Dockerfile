FROM python:3.12-slim
ARG BEACON_VERSION=0.8.3
ARG BEACON_REVISION=unknown
LABEL org.opencontainers.image.title="Beacon Messenger" \
      org.opencontainers.image.source="https://github.com/gigabytegrove/beacon" \
      org.opencontainers.image.version="${BEACON_VERSION}" \
      org.opencontainers.image.revision="${BEACON_REVISION}"
ENV BEACON_VERSION=${BEACON_VERSION} BEACON_REVISION=${BEACON_REVISION}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BEACON_DB=/data/beacon.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 -m beacon && mkdir -p /data && chown beacon:beacon /data
COPY server ./server
USER beacon
EXPOSE 8765
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers"]
