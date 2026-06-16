## Decisions

1. **Pre-observable definition**
   A request is pre-observable when `requests` contains the `request_id` but the record has no bound `run_id`.

2. **Protected endpoints**
   The protection applies only to status, `/events`, `/events/history`, `/chat`, and `/chat/history`.

3. **Status projection**
   Status reads return `queued` with `observability_ready=false` while pre-observable. Once a run is bound and resolvable, responses set `observability_ready=true`.

4. **History projection**
   Event and chat history return `200` with empty `events`, `count=0`, `source="pre_observable"`, and zero cursors.

5. **SSE projection**
   Event and chat SSE endpoints return `200 text/event-stream` and emit a lightweight pre-observable comment frame before closing.

## Risks

- If an already-bound run loses its run directory, it still returns the existing not-found behavior. This avoids hiding cleanup or storage corruption as a normal startup race.
