FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BEACON_DB=/data/beacon.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 -m beacon && mkdir -p /data && chown beacon:beacon /data
COPY server ./server
USER beacon
EXPOSE 8765
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8765", "--proxy-headers", "false"]
