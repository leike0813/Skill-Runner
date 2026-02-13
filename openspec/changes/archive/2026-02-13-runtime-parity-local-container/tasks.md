## 1. 运行时解析与路径统一

- [x] 1.1 新增运行时解析模块，统一输出 mode/platform/data/cache/agent_home/npm_prefix
- [x] 1.2 将 `engine_upgrade_manager` 改为使用运行时解析结果构造子进程环境
- [x] 1.3 改造 `scripts/agent_manager.sh`，移除 `/data` 硬编码兜底
- [x] 1.4 统一其他脚本路径默认值，确保容器/本地一致

## 2. Managed Prefix 与配置隔离

- [x] 2.1 统一 Engine 安装/升级/检测使用 managed prefix
- [x] 2.2 统一 CLI 命令解析优先级（受管 bin 优先）
- [x] 2.3 引入隔离 `agent_home`，避免读取宿主全局配置
- [x] 2.4 新增“仅凭证导入”能力（白名单复制，不导入 settings）

## 3. 本地双平台部署脚本

- [x] 3.1 新增 `scripts/deploy_local.sh`（Linux/macOS）
- [x] 3.2 新增 `scripts/deploy_local.ps1`（Windows）
- [x] 3.3 增加前置检查与失败提示（Node/npm/Python/权限）
- [x] 3.4 文档中补充本地部署与凭证导入说明

## 4. 测试与验证

- [x] 4.1 增加运行时路径解析单元测试（含 Windows 分支）
- [x] 4.2 增加 Engine 升级在 local/container 两模式下的行为一致性测试
- [x] 4.3 验证凭证导入白名单行为（仅 auth 文件）
- [x] 4.4 运行类型检查与单元测试
