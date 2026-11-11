# Bundled cloud client

On 2026-11-11 the owner chose to keep the client inside the integration, matching
other custom integrations in this workspace. This supersedes the separate PyPI
package and publication plan.

`custom_components/velux_active/velux_active_client` contains the single typed,
asynchronous protocol implementation, under the repository's MIT license.
`api.py` preserves the integration's existing API imports. The client receives
Home Assistant's aiohttp session; it never creates a separate session or event loop.
Its request validation, token rotation, bounded retries and shared rate-limit
handling are unchanged by the move.

The HACS ZIP includes the client and its `py.typed` marker. The manifest has no
external requirements. No wheel, PyPI account, publisher configuration or client
release is needed. Home Assistant already supplies aiohttp.

Source tests, strict typing and per-module coverage include the bundled code.
Artifact smoke tests use a fresh aiohttp-only interpreter and verify imports
against the extracted ZIP. The native HA lab verifies installed ZIP members and
client module origins. Release and CI use the same archive.

The protocol follows [pyatmo](https://github.com/jabesq-org/pyatmo) transport and
[ha-velux-active](https://github.com/Niek/ha-velux-active) login references. The
unofficial VELUX password protocol has no published compatibility guarantee.
A future Home Assistant Core submission may require a different dependency
boundary; Core admission is separate from this custom integration's installation.
