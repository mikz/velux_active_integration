# VELUX ACTIVE client

This prepared package provides typed, asynchronous, read-only access to the
VELUX ACTIVE application cloud protocol. Version 0.1.0 is **not yet published**.
It is being extracted without a protocol rewrite from the integration's tested
client; publication follows topology implementation and artifact review.

The caller supplies an aiohttp `ClientSession` and remains responsible for
closing it. The client never closes an injected session. Authenticate with the
existing VELUX app username/password, fetch account topology, fetch each home's
status, and normalize supported modules with `device_from_module`. Device
commands and raw diagnostics exports are not part of this API.

`InvalidAuthError` means credentials/token were rejected. `APIConnectionError`
means transport or supplied data was invalid. `RateLimitError` supplies a bounded
retry deadline, shared across requests. Token refresh is serialized; transient
errors and throttling do not trigger a password login. Null/missing rain means
unknown; supplied rain must be an exact boolean. Anonymous application protocol
identifiers are public source, not account credentials.

Use the public API exported by `velux_active_client`. Treat individual home,
module and account credentials as private. Do not log their representations or
raw responses. Supported execution currently targets Python 3.14.2+ and aiohttp
3.13+; compatibility is accepted through exact-wheel Home Assistant 2026.9.3 and
2026.9.4 labs before release.

Source, issue tracking, MIT license and development acceptance records are in
the public parent repository. See `docs/CLIENT_DEPENDENCY.md` and
`docs/PLATINUM_ACCEPTANCE.md`. A published distribution and exact integration
requirement pin are still open acceptance gates.
