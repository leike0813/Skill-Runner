## Context

The current MCP management section on `/ui/engines` is functional but mirrors the internal registry schema. Users must know MCP transport details, engine root semantics, activation/scope policy, and secret reference behavior before they can configure common servers. Auth entry is the weakest point: a Bearer token requires manually typing a header row in a custom pipe-delimited format.

The existing backend is intentionally strict and should remain stable. The improvement is a browser-side usability layer that produces the same `ManagementMcpServerUpsertRequest` payloads and keeps raw keys write-only.

## Goals / Non-Goals

**Goals:**

- Make common MCP setup understandable without requiring agent-tool-specific config knowledge.
- Preserve all existing advanced capabilities for expert users.
- Support paste/import of native MCP JSON into a previewable form state.
- Keep registry, secret store, management API, resolver, renderer, and runtime behavior unchanged.

**Non-Goals:**

- No online MCP marketplace, remote catalog, or built-in third-party service template registry.
- No new public API that returns raw secrets or changes existing MCP CRUD semantics.
- No changes to skill manifest MCP declarations or runtime engine rendering.

## Decisions

- Implement the improvement in `/ui/engines` as a guided front-end layer over the existing MCP CRUD API. This avoids schema churn and keeps current tests for governance/runtime behavior valid.
- Use typed auth selections in the UI and compile them to existing `auth.env` / `auth.headers` request fields. Blank key values still mean “preserve existing secret” when editing.
- Add native JSON paste/import as a client-side parser with preview. The parser accepts common roots (`mcpServers`, `mcp_servers`, `mcp`) and single-server objects, then populates the same form state used by manual entry.
- Keep an advanced mode but replace free-form pipe/comma syntax with structured rows and newline args. This maintains expert control while removing the most error-prone encoding.
- Surface Claude agent-home persistence as a derived UI summary from existing row data (`claude` in effective engines, `default`, `agent-home`) rather than adding backend state inspection.

## Risks / Trade-offs

- [Risk] Native MCP JSON variants differ across tools. → Mitigation: support only common stdio/http shapes, reject ambiguous objects with a clear UI error, and require preview before save.
- [Risk] Users may expect pasted env/header values to be persisted automatically. → Mitigation: import populates key fields and still requires explicit save.
- [Risk] Advanced mode and guided mode can drift. → Mitigation: use one canonical browser form state and have both modes read/write that state before building the PUT payload.
