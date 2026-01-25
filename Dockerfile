FROM node:24-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    NPM_CONFIG_PREFIX=/opt/cache/npm \
    PATH=/opt/venv/bin:/opt/cache/npm/bin:/usr/local/bin:/usr/bin:/bin \
    UV_CACHE_DIR=/opt/cache/uv_cache \
    UV_PROJECT_ENVIRONMENT=/opt/cache/uv_venv \
    SKILL_RUNNER_DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates \
    ripgrep \
    fd-find \
    fzf \
    sqlite3 \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app /data /opt/cache

WORKDIR /app
COPY pyproject.toml ./
COPY server ./server
COPY skills ./skills

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install uv \
    && /opt/venv/bin/uv pip install --python /opt/venv/bin/python "python-multipart" \
    && /opt/venv/bin/uv pip install --python /opt/venv/bin/python .

COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/agent_manager.sh /app/scripts/agent_manager.sh
COPY scripts/upgrade_agents.sh /app/scripts/upgrade_agents.sh
RUN chmod +x /entrypoint.sh /app/scripts/agent_manager.sh /app/scripts/upgrade_agents.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
