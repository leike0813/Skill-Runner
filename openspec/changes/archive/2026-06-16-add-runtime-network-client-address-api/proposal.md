# Add Runtime Network Client Address API

## Summary

Add a general runtime network diagnostic endpoint that returns the client IP address observed by the Skill Runner backend for the current HTTP request.

## Motivation

Local plugins may need to expose a local service and tell agents which address the backend should use when connecting back to the plugin host. Enumerating local network interfaces on the plugin side is less accurate than asking the backend what peer address it sees for the plugin's request.

## Scope

- Add `GET /v1/runtime/network/client-address`.
- Return a minimal JSON payload containing `client_ip`.
- Do not add Zotero-specific behavior to the API.
- Do not parse untrusted forwarding headers inside this endpoint.

## Non-Goals

- No reverse proxy trust policy changes.
- No endpoint or token persistence.
- No runtime state machine, run store, or event protocol changes.
