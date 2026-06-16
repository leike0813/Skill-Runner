# Design

## API

`GET /v1/runtime/network/client-address` returns:

```json
{
  "client_ip": "203.0.113.10"
}
```

`client_ip` is nullable when the ASGI request scope does not provide a client address.

## Address Source

The endpoint uses `request.client.host`, which represents the peer address visible to the FastAPI/ASGI application. It intentionally does not inspect `X-Forwarded-For`, `Forwarded`, or similar headers because those headers are client-controlled unless a trusted proxy layer normalizes them.

If a deployment needs proxy-aware client identity, that policy should be configured at the ASGI server or reverse proxy boundary so application code receives the trusted peer address consistently.

## Routing

The router is mounted under `/v1/runtime/network` as a generic diagnostic surface, not under Zotero-specific routes.
