# Merge gates

The client is bundled inside the integration ZIP. The former PyPI publication
gate was removed following the owner's 2026-11-11 decision; installation no longer
requires a separately distributed client.

Required validation:

- Locked source tests, strict mypy, Ruff check/format, and per-module branch/line
  coverage (at least 95%; config flow 100%).
- Deterministic ZIP inventory and hashes, including the bundled client and typing
  marker, checked against tracked integration files.
- Clean-interpreter artifact smoke tests with only aiohttp dependencies installed;
  missing client code must fail before cloud I/O.
- Native installed-ZIP acceptance on HA 2026.9.3, 2026.9.4 and 2026.11.1, with
  isolated simulator networking, origin verification and cleanup receipts.
- Hassfest and HACS validation.

Use the current PR checks for results tied to its latest commit. Older standalone
wheel receipts remain historical evidence, not validation of the bundled ZIP.
A simulated rain transition validates software behavior, not physical rain-sensor
freshness. Live deployment checks must separately verify the existing entry and
registry identities are preserved.
