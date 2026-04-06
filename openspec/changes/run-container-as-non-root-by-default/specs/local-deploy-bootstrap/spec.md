## MODIFIED Requirements

### Requirement: Container bootstrap MUST default to non-root runtime execution
系统 MUST 让官方 Docker 镜像与默认 compose 部署以固定非 root 用户运行，避免运行时能力依赖 root/sudo 姿态。

#### Scenario: default compose deployment runs as non-root
- **WHEN** 用户使用仓库默认 `docker-compose.yml` 启动主服务
- **THEN** 容器 MUST 使用镜像内预定义的非 root 用户运行
- **AND** 不要求用户额外设置 `user:` 才能进入受支持的默认部署姿态

#### Scenario: runtime directories remain writable under non-root
- **WHEN** 容器入口脚本在默认镜像中执行 bootstrap 与服务启动
- **THEN** `${SKILL_RUNNER_DATA_DIR}`、agent cache 与 agent home 相关目录 MUST 对该非 root 用户可写
- **AND** 启动链路 MUST 不依赖 root 身份创建这些目录

### Requirement: Optional data bind mount guidance MUST document host-side write requirements
系统 MUST 在默认 compose 与容器部署文档中明确说明：可选 `./data:/data` bind mount 由部署者负责宿主机权限准备。

#### Scenario: compose documents optional data bind mount caveat
- **WHEN** 用户查看仓库默认 `docker-compose.yml`
- **THEN** 文件 MUST 明确提示：如果启用 `./data:/data`，宿主机 `./data` 需要对容器内非 root 用户可写

#### Scenario: docs provide permissive local fallback guidance
- **WHEN** 用户查看容器化部署文档
- **THEN** 文档 MAY 提供诸如 `chmod 777 ./data` 的本地/调试兜底示例
- **AND** MUST 明确这属于部署者自管的可选配置而不是系统默认行为
