## Design Overview

本 change 的核心是“发布源单一化 + terminal 一致性屏障”。

1. 单一发布源  
FCMP/RASP 事件由 `runtime/protocol/live_publish.py` 唯一生成、排序、发往 live journal，并镜像写入 `.audit/*.jsonl`。

2. 查询链路去重算  
`runtime/observability/run_observability.py` 的 `list_protocol_history(stream=fcmp|rasp)` 不再触发 `_materialize_protocol_stream`。  
非 terminal 维持 `audit + live` 合并；terminal 维持 `audit-only`。

3. terminal 前 flush 屏障  
在 terminal 查询分支中先 `flush_live_audit_mirrors(run_id=...)`，等待镜像落盘完成，再读取 audit 文件。  
这样可以避免 terminal 切换瞬间出现“live 里有、audit 里暂未写入”的短窗口。

4. 兼容策略  
历史 `_materialize_protocol_stream` 逻辑保留但脱离查询主链路。  
本 change 不做历史 run 自动修复迁移，避免扩大风险面。
