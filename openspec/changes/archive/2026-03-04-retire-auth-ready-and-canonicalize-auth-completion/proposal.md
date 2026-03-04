## Why

当前 in-conversation auth 体系仍残留早期的 `auth_ready` 语义。该语义最初用于表示 engine 凭据“看起来已经就绪”，但它被错误复用成了 auth session completion 判据，导致：

- `waiting_auth` 可在用户未完成 challenge 时被错误推进到 `queued`
- observability 的 detail/list 轮询会触发错误 resume
- 单方式 busy recovery 有机会被误判成 completion
- runtime、orchestration、engine observability、docs、spec、tests 对 auth 完成语义不一致

本 change 要做的是系统性退役 `auth_ready`，并把 `auth.completed`、resume ticket、`waiting_auth -> queued` 的唯一合法来源统一为 canonical auth completion。

## What Changes

- 在整个代码库移除 `auth_ready` 作为 runtime/auth completion 语义
- 将 auth completion 统一收敛到：
  - session snapshot `status in {"succeeded", "completed"}`
  - 或显式 callback/submission completion path
- 收紧 waiting_auth reconcile、resume issuance、FCMP `auth.completed` 生成逻辑，禁止 readiness-like 信号推进流程
- 将 engine static auth observability 改成非 completion 语义字段，默认使用 `credential_state`
- 更新 SSOT、docs、OpenSpec specs、schema、模型测试和场景回归

## Impact

- management / engine auth observability 不再返回 `auth_ready`
- waiting_auth 相关自动 reconcile 将变成 completion-only，避免无用户操作的 resume loop
- auth session runtime、orchestration、protocol、observability 的语义边界会更清晰：
  - static credential state 只用于观测
  - canonical auth completion 才能驱动 resume
