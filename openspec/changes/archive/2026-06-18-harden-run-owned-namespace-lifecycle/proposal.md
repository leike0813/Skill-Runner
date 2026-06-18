# Proposal: harden run-owned namespace lifecycle

## Summary

Request-bound runs that use a run-owned workspace namespace must use that namespace consistently for state, result, input-manifest, audit, protocol, chat replay, log, interaction, and auth lifecycle files. Recent workspace-reuse work introduced namespaced runner-owned paths, but several lifecycle edges still wrote or read legacy root paths. This follow-up hardens the full lifecycle so frontend status, run list, event/chat history, logs, result, bundle, cancel, reply, and auth flows observe the same canonical run state.

## Problem

For reused workspaces, multiple logical runs share one physical workspace. If one writer still updates `.state/state.json` or `.audit/*.jsonl` while another reader prefers `result/<namespace>/result.json` or `.state/<namespace>/state.json`, the system can split truth across paths. The observed failure mode was a run detail reading succeeded state while the run list still displayed running. The same class of bug also affects frontend communication because status, events, chat, and logs can disagree.

The root cause is not a single endpoint; it is lifecycle leakage. Request creation persisted namespace metadata, but some later phases bypassed the layout resolver:

- execution-time live FCMP/RASP/chat mirrors and overflow sidecars could write root `.audit`;
- list/detail/result/log/cancel readers could fall back to root state too early;
- interaction reply and auth recovery callbacks could emit audit events or state updates through legacy orchestrator helpers.

## Goals

- Treat persisted workspace layout metadata as the source of truth for every request-bound run file path.
- Keep legacy root paths readable only as fallback for historical runs or no-layout execution.
- Prevent request-bound writers from creating new split-brain state or audit files in root `.state` / `.audit`.
- Preserve terminal result and bundle behavior around actual `resultJsonPath`.
- Add targeted regression coverage for lifecycle edges that previously bypassed layout resolution.

## Non-Goals

- Do not remove legacy root-path fallback support for old runs.
- Do not migrate historical run directories.
- Do not change the canonical state machine or add new statuses.
- Do not change public response shapes beyond already exposed path diagnostics.
- Do not redesign workspace namespace allocation.
