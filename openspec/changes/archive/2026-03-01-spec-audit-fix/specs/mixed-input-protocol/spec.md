# mixed-input-protocol Specification

## Purpose
定义 input 的 inline payload 支持和显式来源声明约束。

## MODIFIED Requirements

### Requirement: `input` MUST support inline payload via request body
系统 MUST 支持客户端在 `POST /v1/jobs` 请求体中直接提供 `input` JSON。

#### Scenario: inline input create request
- **WHEN** skill 的 input 字段被声明为 inline 来源
- **AND** 客户端在请求体中提供对应 `input.<key>`
- **THEN** 系统接受并保存该值用于后续执行
