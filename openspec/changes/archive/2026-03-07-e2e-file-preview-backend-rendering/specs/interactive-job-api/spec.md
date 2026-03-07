## ADDED Requirements

### Requirement: 系统 MUST 提供 jobs 主链路 run 文件树读取接口
系统 MUST 提供 `GET /v1/jobs/{request_id}/files`，用于返回当前 run 的可浏览文件树条目。

#### Scenario: 客户端读取 run 文件树
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/files`
- **THEN** 服务返回 run scope 的文件树条目列表
- **AND** 每个条目至少包含 `path/name/is_dir/depth`

### Requirement: 系统 MUST 提供 jobs 主链路 run 文件预览接口
系统 MUST 提供 `GET /v1/jobs/{request_id}/file?path=...`，并返回后端 canonical 预览载荷。

#### Scenario: 客户端读取文本文件预览
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/file?path=...`
- **THEN** 服务返回 `preview` 载荷
- **AND** 载荷包含兼容字段 `mode/content/meta/size`
- **AND** 载荷可选包含扩展字段 `detected_format/rendered_html/json_pretty`

#### Scenario: 非法路径请求被拒绝
- **WHEN** 客户端传入绝对路径、`..` 或无效路径
- **THEN** 服务返回 `400`
- **AND** 不读取 run 目录外文件
