FROM python:3.12-slim
ARG BEACON_VERSION=0.9.2
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
# Prevent deployment of an image whose Python modules fail to parse/import.
# This fails the build BEFORE the existing Beacon service is touched.
RUN python -m compileall -q server \
    && python -c "from server.main import app; assert app is not None" \
    && chmod -R u=rwX,go=rX /app/server
# Keep installed application code root-owned (not writable by the runtime user).
# Normalize checkout permissions: a root clone with umask 077 gives files 0600
# and directories 0700, which would otherwise break the unprivileged launcher.
USER beacon
# Fail the image build if the actual runtime user cannot import the application.
RUN python -c "import os; from pathlib import Path; p=Path('/app/server/__init__.py'); assert p.is_file(); p.read_bytes(); assert not os.access(p, os.W_OK); from server.main import app; assert app is not None"
EXPOSE 8765
CMD ["python", "-m", "server.launcher"]
