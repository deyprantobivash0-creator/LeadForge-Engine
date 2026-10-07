FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt ./
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt && pip check \
    && groupadd --gid 10001 leadforge \
    && useradd --uid 10001 --gid leadforge --no-create-home leadforge

# Explicit copies prevent unrelated development artifacts entering image layers.
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--no-access-log", "--no-server-header", "--timeout-graceful-shutdown", "30"]
