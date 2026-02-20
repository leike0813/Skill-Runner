# Built-in E2E Example Client UI Reference

## 1. Scope

This document defines the UI information architecture and interaction conventions for the built-in E2E example client (`e2e_client/`).

Goals:
- Simulate a real external client workflow.
- Keep implementation independent from `server/`.
- Provide deterministic pages for E2E and regression tests.

## 2. Service Boundary

- Service is standalone (`e2e_client/app.py`) and runs on a dedicated port.
- Default port is `8011`.
- `SKILL_RUNNER_E2E_CLIENT_PORT` overrides the port; invalid values fallback to `8011`.
- Client accesses backend only through HTTP APIs (`/v1/management/*`, `/v1/jobs*`).

## 3. Navigation Structure

Primary routes:
- `/`: skill list page.
- `/skills/{skill_id}/run`: schema-driven execution form.
- `/runs/{request_id}`: run observation page.
- `/runs/{request_id}/result`: result and artifact view.
- `/recordings`: recording list.
- `/recordings/{request_id}`: single-step replay view.

## 4. Page Layouts

### 4.1 Skill List
- Table columns: skill name/id, version, engines, health, action.
- Action button opens run form.

### 4.2 Run Form
- Engine selector at top.
- Execution mode selector at top (values from backend `execution_modes`).
- Model selector at top (values from management engine detail by selected engine).
- Three blocks:
  - Inline input fields.
  - Parameter fields.
  - File upload fields.
- Runtime options block:
  - booleans: `verbose/no_cache/debug/debug_keep_temp`
  - interaction policy: `interactive_require_user_reply`
  - timeout options: `session_timeout_sec/interactive_wait_timeout_sec/hard_wait_timeout_sec/wait_timeout_sec`
- Validation errors shown inline at top.
- Submit action:
  1. `POST /v1/jobs`
  2. Optional `POST /v1/jobs/{request_id}/upload` with generated zip

### 4.3 Run Observation
- Header: status + pending interaction id + shortcuts (result/replay).
- Main area:
  - Left: stdout conversation panel (scrollable, fixed height).
  - Right: stderr panel (separate scrollable window).
- Bottom interaction area:
  - pending prompt text.
  - user reply textbox + submit button.
- Status sync:
  - consume SSE from `/api/runs/{request_id}/events`.
  - when `waiting_user`, fetch pending and enable reply.
  - when terminal, stop streaming and lock input.

### 4.4 Result View
- Left: formatted result JSON.
- Right: artifact list and download links.
- Additional bundle explorer:
  - file tree (scrollable, fixed-height)
  - file preview panel (text preview with binary/large-file fallback)

### 4.5 Replay View (Single-step)
- Step counter and `Prev/Next` controls.
- Current step panel shows:
  - timestamp
  - action
  - request/response summary payload

## 5. Recording Model (MVP)

Stored in `e2e_client/recordings/{request_id}.json`.

Each step stores:
- `ts`
- `action`
- `status`
- `request` summary
- `response` summary

Tracked actions in MVP:
- `create_run`
- `upload`
- `reply`
- `result_read`

## 6. Interaction Rules

- Reply submit is enabled only when `pending` exists.
- File inputs are zipped using schema key names as zip entry names.
- Type parsing for inline/parameter inputs:
  - integer/number/boolean coercion
  - object/array via JSON parse
- Invalid input blocks submission and keeps user-entered values.
- Invalid execution mode selection is rejected before request submission.

## 7. Testability Requirements

- All key user actions must be reachable with plain HTTP + HTML forms.
- Replay payload is accessible via `GET /api/recordings/{request_id}`.
- Observation stream is accessible via `GET /api/runs/{request_id}/events`.
