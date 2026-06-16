## Summary

Protect clients that read observability endpoints immediately after receiving a `request_id`.

When a request exists but no run has been bound yet, status, event history, chat history, and their SSE endpoints should return stable pre-observable responses instead of `404 Run not found`.

## Motivation

`POST /v1/jobs` can return a request before the request has a materialized run, most visibly for temporary skill upload flows. Frontends may optimistically start polling status, events, or chat as soon as they receive the `request_id`. Treating that race as a missing resource makes normal early polling look like an error.

## Impact

- Missing request IDs still return `404`.
- Existing-but-not-yet-observable requests return safe empty observability responses.
- Run-dependent artifact/result/file endpoints remain unchanged.
