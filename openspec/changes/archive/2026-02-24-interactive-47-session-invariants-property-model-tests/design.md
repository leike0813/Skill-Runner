## Overview

本变更将“session + FCMP 核心不变量”抽离为单一 YAML 合同，并由属性/模型测试直接消费，以形成可执行文档约束。

## Decision 1: YAML 作为不变量 SSOT

- 文件：`docs/contracts/session_fcmp_invariants.yaml`
- 结构固定：
  - `version`
  - `canonical`
  - `transitions`
  - `fcmp_mapping`
  - `ordering_rules`

该文件仅作为文档合同源，不直接参与运行时代码分支。

## Decision 2: 无新依赖的模型测试

- 不引入 Hypothesis；
- 使用 pytest + 有限状态空间枚举（有限深度事件序列）；
- 使用 transition index 做模型/实现等价校验。

## Decision 3: 核心范围收敛

仅覆盖：

1. session canonical 状态机不变量；
2. FCMP `conversation.state.changed` 映射不变量；
3. reply/auto-decide 配对不变量与事件序不变量。

不扩展至 store/SSE 全链路模型测试。

## Contract-to-Test Mapping

1. `test_session_invariant_contract.py`
- 校验 YAML 结构、状态集合、转移集合与实现一致性。

2. `test_session_state_model_properties.py`
- 校验可达性、终态无出边、等待态出边边界、模型与实现在有限事件序列上等价。

3. `test_fcmp_mapping_properties.py`
- 校验 `conversation.state.changed` 三元组属于合同映射；
- 校验 paired event 与 state_changed 配对；
- 校验 terminal 语义一致；
- 校验 `seq` 连续递增。

## Failure Semantics

- 合同漂移（文档改动未同步实现/测试）将直接导致单测失败；
- 映射漂移（实现输出未覆盖合同）将直接导致属性测试失败。
