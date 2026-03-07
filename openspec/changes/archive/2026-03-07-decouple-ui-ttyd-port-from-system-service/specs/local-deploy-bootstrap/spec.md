## ADDED Requirements

### Requirement: 部署示例 MUST 使用与系统 ttyd 解耦的高位默认端口
系统 MUST 在本地与容器部署示例中使用高位默认 ttyd 端口，避免与宿主机系统 `ttyd.service` 默认端口冲突。

#### Scenario: compose 默认端口
- **WHEN** 用户使用仓库默认 compose 文件部署
- **THEN** 内嵌 ttyd 映射端口默认为 `17681`
- **AND** 不占用 `7681`

#### Scenario: docker run 示例端口
- **WHEN** 用户参考 README 的 docker run 示例部署
- **THEN** ttyd 映射端口示例为 `17681:17681`
- **AND** 示例文案与 compose 配置一致

### Requirement: compose ttyd 映射 MUST 采用同号映射并提示不要拆分
系统 MUST 在 compose 中采用同号端口映射，并提示用户不要仅修改 host 或 container 端口的单侧值。

#### Scenario: compose 注释提示
- **WHEN** 用户查看 compose ttyd 端口配置
- **THEN** 文件包含“host/container 保持同号映射”的明确提示
- **AND** 默认配置为 `17681:17681`
