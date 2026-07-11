# datetime.utcnow() 弃用修复报告

**生成日期**: 2026-06-23
**影响范围**: 99 处调用，~30 个文件
**Python 最低版本**: >= 3.11（`datetime.UTC` 可用）
**修复策略**: 接受 `.isoformat()` 输出从 naive 变为 aware（`+00:00` 后缀）

---

## 1. 背景

`datetime.datetime.utcnow()` 自 Python 3.12 起被标记为弃用，返回 naive datetime 对象（无时区信息）。官方建议改用 `datetime.datetime.now(datetime.UTC)` 或 `datetime.datetime.now(datetime.timezone.utc)` 返回 timezone-aware 对象。

本项目 Python >= 3.11，`datetime.UTC`（3.11 新增）可用。

## 2. 统一修改规则

### 2.1 导入变更

```python
# 旧
from datetime import datetime

# 新
from datetime import datetime, timezone
```

对于已有 `from datetime import datetime, timezone` 的文件，无需修改导入。

### 2.2 替换规则

| 原代码 | 替换为 | 说明 |
|--------|--------|------|
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | 直接替换，返回 aware datetime |
| `datetime.utcnow().isoformat()` | `datetime.now(timezone.utc).isoformat()` | 输出从 `"..."` 变为 `"...+00:00"` |
| `datetime.utcnow().isoformat() + "Z"` | `datetime.now(timezone.utc).isoformat()` | 已带 `+00:00`，无需追加 `Z`；若需 `Z` 结尾可用 `.replace("+00:00", "Z")` |
| `datetime.utcnow().strftime("...Z")` | `datetime.now(timezone.utc).strftime("...Z")` | `%S` 后的 `Z` 是字面量，输出不变 |
| `field(default_factory=datetime.utcnow)` | `field(default_factory=lambda: datetime.now(timezone.utc))` | dataclass 默认工厂 |
| `datetime.utcnow() + timedelta(...)` | `datetime.now(timezone.utc) + timedelta(...)` | aware datetime 支持 timedelta 运算 |
| `datetime.utcnow().astimezone(tz)` | `datetime.now(timezone.utc).astimezone(tz)` | aware datetime 同样支持 astimezone |

### 2.3 格式兼容性说明

**关键变化**: `.isoformat()` 输出会新增 `+00:00` 后缀。

```
旧: "2024-01-01T12:00:00.123456"
新: "2024-01-01T12:00:00.123456+00:00"
```

**影响评估**:
- **读取侧**: 项目中多处已有 `replace("Z", "+00:00")` 的解析逻辑（`management.py:1072/1088`、`jobs.py:278`、`run_store_auth_state_store.py:598/606/607`、`run_recovery_service.py:23`、`run_auth_orchestration_service.py:90`），已能处理 `+00:00` 格式。
- **写入侧**: 项目中已有 ~90+ 处使用 `datetime.now(timezone.utc).isoformat()` 输出带 `+00:00` 的格式，说明系统已在此格式下运行。
- ** strftime 场景**: 格式字符串中的 `Z` 是字面量（不是 `%Z`），输出不受影响。

## 3. 逐文件修改明细

### 3.1 server/services/orchestration/

#### `server/services/orchestration/run_store_auth_state_store.py` (12 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 62 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 121 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 143 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 174 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 210 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 253 | `now = datetime.utcnow().isoformat() + "Z"` | `now = datetime.now(timezone.utc).isoformat()` |
| 452 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 467 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 482 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 518 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 556 | `server_now = datetime.utcnow().isoformat() + "Z"` | `server_now = datetime.now(timezone.utc).isoformat()` |
| 602 | `datetime.utcnow().astimezone(expires_at_dt.tzinfo)` | `datetime.now(timezone.utc).astimezone(expires_at_dt.tzinfo)` |

> **注意 L253, L556**: 原代码追加 `"Z"` 是因为旧代码输出 naive ISO 格式，需要手动标记 UTC。替换为 aware datetime 后 `.isoformat()` 自带 `+00:00`，不再需要 `"Z"`。但需确认下游消费方是否依赖 `Z` 结尾格式。如有依赖，改用 `datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")`。

---

#### `server/services/orchestration/run_store_interaction_store.py` (7 处)

**导入**: `from datetime import datetime, timedelta` → `from datetime import datetime, timedelta, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 32 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 127 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 155 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 192 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 270 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 408 | `("consumed", datetime.utcnow().isoformat(), ...)` | `("consumed", datetime.now(timezone.utc).isoformat(), ...)` |
| 445 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/orchestration/run_store_cache_store.py` (4 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 32 | `created_at = datetime.utcnow().isoformat()` | `created_at = datetime.now(timezone.utc).isoformat()` |
| 67 | `updated_at = datetime.utcnow().isoformat()` | `updated_at = datetime.now(timezone.utc).isoformat()` |
| 112 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 157 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/orchestration/run_store_state_store.py` (3 处)

**导入**: `from datetime import datetime, timedelta` → `from datetime import datetime, timedelta, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 190 | `updated_at = datetime.utcnow()` | `updated_at = datetime.now(timezone.utc)` |
| 275 | `cutoff = datetime.utcnow() - timedelta(days=retention_days)` | `cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)` |
| 533 | `recovered_ts = recovered_at or datetime.utcnow().isoformat()` | `recovered_ts = recovered_at or datetime.now(timezone.utc).isoformat()` |

> **注意 L190**: 此处 `updated_at` 是 naive datetime 对象，改为 aware 后需确认该字段在后续比较/序列化链路中不会有 naive/aware 混用问题。

---

#### `server/services/orchestration/run_store_request_store.py` (2 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 33 | `created_at = datetime.utcnow().isoformat()` | `created_at = datetime.now(timezone.utc).isoformat()` |
| 487 | `created_at = datetime.utcnow().isoformat()` | `created_at = datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/orchestration/run_store_database.py` (1 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 40 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/orchestration/run_state_service.py` (3 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 250 | `updated_at = datetime.utcnow()` | `updated_at = datetime.now(timezone.utc)` |
| 295 | `now = datetime.utcnow()` | `now = datetime.now(timezone.utc)` |
| 386 | `updated_at = datetime.utcnow()` | `updated_at = datetime.now(timezone.utc)` |

---

#### `server/services/orchestration/run_job_lifecycle_service.py` (2 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 306 | `attempt_started_at: datetime = field(default_factory=datetime.utcnow)` | `attempt_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))` |
| 710 | `attempt_started_at = datetime.utcnow()` | `attempt_started_at = datetime.now(timezone.utc)` |
| 1228 | `finished_at=datetime.utcnow()` | `finished_at=datetime.now(timezone.utc)` |

---

#### `server/services/orchestration/run_interaction_lifecycle_service.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 105 | `"resolved_at": datetime.utcnow().isoformat()` | `"resolved_at": datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/orchestration/run_cleanup_manager.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 40 | `logger.info("Run cleanup started at %s", datetime.utcnow().isoformat())` | `logger.info("Run cleanup started at %s", datetime.now(timezone.utc).isoformat())` |

---

#### `server/services/orchestration/run_audit_service.py` (4 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 406 | `"ts": datetime.utcnow().isoformat()` | `"ts": datetime.now(timezone.utc).isoformat()` |
| 468 | `ts=datetime.utcnow().isoformat()` | `ts=datetime.now(timezone.utc).isoformat()` |
| 490 | `updated_at=datetime.utcnow().isoformat()` | `updated_at=datetime.now(timezone.utc).isoformat()` |
| 500 | `ts=datetime.utcnow()` | `ts=datetime.now(timezone.utc)` |

---

#### `server/services/orchestration/run_audit_contract_service.py` (2 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 105 | `created_at=datetime.utcnow()` | `created_at=datetime.now(timezone.utc)` |
| 145 | `"created_at": datetime.utcnow().isoformat()` | `"created_at": datetime.now(timezone.utc).isoformat()` |

---

### 3.2 server/runtime/protocol/

#### `server/runtime/protocol/live_publish.py` (15 处)

**导入**: 需确认是否已有 `timezone`

所有 15 处均为 `ts=event_ts or datetime.utcnow()` 模式：

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 1041 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1115 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1131 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1154 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1192 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1202 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1253 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1263 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1334 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1344 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1389 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1457 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1467 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1479 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |
| 1489 | `ts=event_ts or datetime.utcnow()` | `ts=event_ts or datetime.now(timezone.utc)` |

---

#### `server/runtime/protocol/factories.py` (3 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 33 | `ts=ts or datetime.utcnow()` | `ts=ts or datetime.now(timezone.utc)` |
| 57 | `ts=ts or datetime.utcnow()` | `ts=ts or datetime.now(timezone.utc)` |
| 302 | `"ts": ts or datetime.utcnow().isoformat()` | `"ts": ts or datetime.now(timezone.utc).isoformat()` |

---

#### `server/runtime/protocol/event_protocol.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 67 | `return datetime.utcnow()` | `return datetime.now(timezone.utc)` |

---

### 3.3 server/runtime/ 其他

#### `server/runtime/observability/run_observability.py` (4 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 445 | `yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}` | `yield {"event": "heartbeat", "data": {"ts": datetime.now(timezone.utc).isoformat()}}` |
| 553 | `yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}` | `yield {"event": "heartbeat", "data": {"ts": datetime.now(timezone.utc).isoformat()}}` |
| 2349 | `timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")` | `timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")` |
| 2480 | `"ts": datetime.utcnow().isoformat()` | `"ts": datetime.now(timezone.utc).isoformat()` |

---

#### `server/runtime/chat_replay/publisher.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 104 | `row["created_at"] = datetime.utcnow().isoformat()` | `row["created_at"] = datetime.now(timezone.utc).isoformat()` |

---

#### `server/runtime/chat_replay/factories.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 28 | `created_at=created_at or datetime.utcnow()` | `created_at=created_at or datetime.now(timezone.utc)` |

---

#### `server/runtime/adapter/base_execution_adapter.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 881 | `"ts": datetime.utcnow().isoformat()` | `"ts": datetime.now(timezone.utc).isoformat()` |

---

### 3.4 server/services/ 其他

#### `server/services/skill/skill_install_store.py` (2 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 135 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 179 | `fields["updated_at"] = datetime.utcnow().isoformat()` | `fields["updated_at"] = datetime.now(timezone.utc).isoformat()` |

---

#### `server/services/skill/temp_skill_package_cache_service.py` (2 处)

**导入**: `from datetime import datetime, timedelta` → `from datetime import datetime, timedelta, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 91 | `now_iso = datetime.utcnow().isoformat()` | `now_iso = datetime.now(timezone.utc).isoformat()` |
| 141 | `return (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()` | `return (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()` |

---

#### `server/services/skill/skill_package_manager.py` (1 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 174 | `timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")` | `timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")` |

> `strftime` 格式中 `%S` 是秒，`Z` 是字面量字符，输出不变。

---

#### `server/services/engine_management/engine_upgrade_store.py` (2 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 60 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |
| 89 | `updates: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}` | `updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}` |

---

### 3.5 server/engines/

#### `server/engines/claude/auth/protocol/oauth_proxy_flow.py` (1 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 30 | `return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")` | `return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` |

---

### 3.6 server/routers/

#### `server/routers/skill_packages.py` (1 处)

**导入**: `from datetime import datetime` → `from datetime import datetime, timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 68 | `created_at = datetime.utcnow()` | `created_at = datetime.now(timezone.utc)` |

---

### 3.7 agent_harness/

#### `agent_harness/storage.py` (2 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 40 | `run_id = f"{datetime.utcnow():%Y%m%dT%H%M%S}-{engine}-{uuid4().hex[:8]}"` | `run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{engine}-{uuid4().hex[:8]}"` |
| 195 | `payload["updated_at"] = datetime.utcnow().isoformat()` | `payload["updated_at"] = datetime.now(timezone.utc).isoformat()` |

> **注意 L40**: f-string 中的 `:%Y%m%dT%H%M%S` 是 strftime 格式化，aware datetime 同样支持，输出不变。

---

#### `agent_harness/runtime.py` (3 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 660 | `"updated_at": datetime.utcnow().isoformat()` | `"updated_at": datetime.now(timezone.utc).isoformat()` |
| 701 | `"started_at": datetime.utcnow().isoformat()` | `"started_at": datetime.now(timezone.utc).isoformat()` |
| 702 | `"finished_at": datetime.utcnow().isoformat()` | `"finished_at": datetime.now(timezone.utc).isoformat()` |

---

### 3.8 tests/unit/

#### `tests/unit/test_run_cleanup_manager.py` (6 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 66 | `now = datetime.utcnow()` | `now = datetime.now(timezone.utc)` |
| 131 | `old_ts = (datetime.utcnow() - timedelta(days=3)).isoformat()` | `old_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()` |
| 221 | `... RunStatus.SUCCEEDED, (datetime.utcnow() - timedelta(days=10)).isoformat())` | `... RunStatus.SUCCEEDED, (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())` |
| 313 | `old_ts = datetime.utcnow() - timedelta(days=5)` | `old_ts = datetime.now(timezone.utc) - timedelta(days=5)` |
| 327 | `closed_at=(datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")` | `closed_at=(datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")` |
| 342 | `old_ts = datetime.utcnow() - timedelta(days=5)` | `old_ts = datetime.now(timezone.utc) - timedelta(days=5)` |

---

#### `tests/unit/test_fcmp_interaction_dedup.py` (3 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 26 | `ts=datetime.utcnow()` | `ts=datetime.now(timezone.utc)` |
| 36 | `ts=datetime.utcnow()` | `ts=datetime.now(timezone.utc)` |
| 46 | `ts=datetime.utcnow()` | `ts=datetime.now(timezone.utc)` |

---

#### `tests/unit/test_live_publish_ordering.py` (3 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 37 | `"ts": datetime.utcnow().isoformat()` | `"ts": datetime.now(timezone.utc).isoformat()` |
| 83 | `ts=datetime.utcnow()` | `ts=datetime.now(timezone.utc)` |
| 294 | `"ts": datetime.utcnow().isoformat()` | `"ts": datetime.now(timezone.utc).isoformat()` |

---

#### `tests/unit/test_auth_detection_audit_persistence.py` (4 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 24 | `started_at=datetime.utcnow()` | `started_at=datetime.now(timezone.utc)` |
| 25 | `finished_at=datetime.utcnow()` | `finished_at=datetime.now(timezone.utc)` |
| 81 | `started_at=datetime.utcnow()` | `started_at=datetime.now(timezone.utc)` |
| 82 | `finished_at=datetime.utcnow()` | `finished_at=datetime.now(timezone.utc)` |

---

#### `tests/unit/test_skill_packages_router.py` (1 处)

**导入**: 需确认是否已有 `timezone`

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 65 | `now = datetime.utcnow().isoformat()` | `now = datetime.now(timezone.utc).isoformat()` |

---

## 4. 需特别关注的兼容性风险

### 4.1 L253, L556 — `run_store_auth_state_store.py` 的 `+ "Z"` 后缀

原代码 `datetime.utcnow().isoformat() + "Z"` 显式追加 `Z` 标记 UTC。替换后 `.isoformat()` 自带 `+00:00`，需确认下游消费方是否期望 `Z` 结尾。若需要保持 `Z` 结尾：

```python
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```

### 4.2 naive/aware 比较兼容性

以下位置原先返回 naive datetime 对象，替换后变为 aware：
- `run_store_state_store.py:190` — `updated_at = datetime.utcnow()`
- `run_state_service.py:250/295/386` — `updated_at`/`now` 赋值
- `run_audit_contract_service.py:105` — `created_at=datetime.utcnow()`
- `run_job_lifecycle_service.py:306/710/1228` — `attempt_started_at`/`finished_at`
- `chat_replay/factories.py:28` — `created_at`
- `event_protocol.py:67` — 函数返回值
- `skill_packages.py:68` — `created_at`

如果这些 datetime 对象后续与数据库中读取的 naive datetime 进行比较（如 `updated_at > other_ts`），会产生 `TypeError: can't compare offset-naive and offset-aware datetimes`。需要检查这些字段的完整生命周期。

### 4.3 dataclass default_factory 变更

`run_job_lifecycle_service.py:306` 的 `field(default_factory=datetime.utcnow)` 需改为 lambda 形式：

```python
attempt_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### 4.4 f-string 格式化

`agent_harness/storage.py:40` 使用 f-string 格式化 datetime：

```python
f"{datetime.utcnow():%Y%m%dT%H%M%S}-..."
```

aware datetime 同样支持 `:%Y%m%dT%H%M%S` 格式化，输出不变。

## 5. 建议执行顺序

1. **先修测试文件**（5 个文件，17 处）— 消除运行测试时的 DeprecationWarning
2. **再修高频文件**（`live_publish.py` 15 处, `run_store_auth_state_store.py` 12 处, `run_store_interaction_store.py` 7 处）
3. **最后修其余生产代码**（按模块逐个处理）
4. 每修改一个模块后立即运行该模块相关测试，确认无 naive/aware 比较异常

## 6. 统计汇总

| 区域 | 文件数 | 调用数 |
|------|--------|--------|
| server/services/orchestration/ | 10 | 40 |
| server/runtime/protocol/ | 3 | 19 |
| server/runtime/ 其他 | 4 | 7 |
| server/services/skill/ | 3 | 5 |
| server/services/engine_management/ | 1 | 2 |
| server/engines/ | 1 | 1 |
| server/routers/ | 1 | 1 |
| agent_harness/ | 2 | 5 |
| tests/unit/ | 5 | 17 |
| **合计** | **30** | **97** |

> 注：加上 `run_job_lifecycle_service.py:1228` 和 `oauth_proxy_flow.py:30` 共 2 处遗漏，总计 **99 处**。
