FROM node:24-bookworm-slim
ARG TARGETARCH
ARG TTYD_VERSION=1.7.7

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    SKILL_RUNNER_RUNTIME_MODE=container \
    SKILL_RUNNER_AGENT_CACHE_DIR=/opt/cache/skill-runner \
    SKILL_RUNNER_AGENT_HOME=/opt/cache/skill-runner/agent-home \
    SKILL_RUNNER_NPM_PREFIX=/opt/cache/skill-runner/npm \
    NPM_CONFIG_PREFIX=/opt/cache/skill-runner/npm \
    PATH=/opt/venv/bin:/opt/cache/skill-runner/npm/bin:/usr/local/bin:/usr/bin:/bin \
    UV_CACHE_DIR=/opt/cache/skill-runner/uv_cache \
    UV_PROJECT_ENVIRONMENT=/opt/cache/skill-runner/uv_venv \
    SKILL_RUNNER_DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates \
    curl \
    git \
    ripgrep \
    fd-find \
    fzf \
    sqlite3 \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app /data /opt/cache /opt/config \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
    && case "${TARGETARCH}" in \
         amd64) ttyd_arch="x86_64" ;; \
         arm64) ttyd_arch="aarch64" ;; \
         *) echo "Unsupported TARGETARCH for ttyd: ${TARGETARCH}" >&2; exit 1 ;; \
       esac \
    && curl -fsSL --retry 3 --retry-delay 1 \
       -o /usr/local/bin/ttyd \
       "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ttyd_arch}" \
    && chmod +x /usr/local/bin/ttyd \
    && /usr/local/bin/ttyd --help >/dev/null

WORKDIR /app
COPY pyproject.toml ./
COPY server ./server
COPY skills ./skills

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install uv \
    && /opt/venv/bin/uv pip install --python /opt/venv/bin/python .

COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/agent_manager.sh /app/scripts/agent_manager.sh
COPY scripts/agent_manager.py /app/scripts/agent_manager.py
COPY scripts/upgrade_agents.sh /app/scripts/upgrade_agents.sh
COPY scripts/deploy_local.sh /app/scripts/deploy_local.sh
RUN chmod +x /entrypoint.sh /app/scripts/agent_manager.sh /app/scripts/upgrade_agents.sh /app/scripts/deploy_local.sh

EXPOSE 8000 7681

ENTRYPOINT ["/entrypoint.sh"]
