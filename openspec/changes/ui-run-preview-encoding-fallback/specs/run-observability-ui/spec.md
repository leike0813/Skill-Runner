## MODIFIED Requirements

### Requirement: 系统 MUST 支持 Run 文件只读预览
系统 MUST 允许用户在 UI 中预览 run 目录文件内容，且不得提供修改入口。二进制检测 MUST 基于启发式（`NUL` 字节与控制字符比例），而不是“UTF-8 解码失败即二进制”。文本解码 MUST 按 `utf-8`、`utf-8-sig`、`gb18030`、`big5` 顺序回退。

#### Scenario: 预览 UTF-8 文本文件
- **WHEN** 用户请求 `/ui/runs/{request_id}/view?path=<relative_path>`
- **AND** 目标文件在大小阈值内且判定为文本
- **THEN** 系统返回对应文件预览内容
- **AND** 元信息标记命中编码（`utf-8` 或 `utf-8-sig`）
- **AND** 仅允许 run 目录内的安全路径

#### Scenario: 预览非 UTF-8 文本文件
- **WHEN** 用户请求预览 gb18030 或 big5 编码的 Markdown/文本文件
- **AND** 文件不含 `NUL` 且控制字符比例未超过二进制阈值
- **THEN** 系统不得将该文件判定为二进制
- **AND** 系统按回退顺序解码并返回文本预览
- **AND** 元信息标记命中编码（`gb18030` 或 `big5`）

#### Scenario: 启发式判定为二进制文件
- **WHEN** 目标文件样本包含 `NUL` 字节，或控制字符比例超过阈值
- **THEN** 系统返回“不可预览”降级结果
- **AND** 不返回原始文件内容

#### Scenario: 非法路径被拒绝
- **WHEN** 用户请求路径越界或文件不存在
- **THEN** 系统返回错误响应（400 或 404）
