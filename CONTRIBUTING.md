# Contribute

Create a branch from `main`, add a regression case for the changed behavior,
and open a pull request. Use synthetic fixtures; do not commit account credentials,
tokens, device exports, or raw production logs.

Run the source checks and isolated Home Assistant lab described in the
[README](README.md). Integration changes must preserve existing entity unique IDs
and the username/password config-entry format. Test the exact release archive.
Keep the cloud simulator under `tests/lab`, outside the installed integration.

The lab controller, route validation, redaction, and preview relay were adapted
from [ha-operator](https://github.com/mikz/ha-operator) under the MIT license.
Contributions to this repository use the [MIT license](LICENSE).

## Runtime architecture and identity

`api.py` is the inline, asynchronous cloud client. It receives Home Assistant's
shared `aiohttp.ClientSession`; it does not create or close that session. The
client implements bounded HTTP requests, token rotation under an async lock,
read-only topology/status endpoints, and a monotonic Retry-After deadline.
`coordinator.py` owns polling and translates authentication failures into
`ConfigEntryAuthFailed`, and connectivity/rate failures into `UpdateFailed`.
Home Assistant supplies first-refresh validation, retry scheduling, and one
outage/recovery log pair. The typed config-entry alias stores the coordinator in
`runtime_data`. All three read-only platforms specify `PARALLEL_UPDATES = 0`.

`entity.py` supplies device identity and current-snapshot availability. Entities
subscribe and unsubscribe through `CoordinatorEntity` lifecycle methods. Their
names describe only the measurement; Home Assistant adds the device name. A
cover is its device's main entity. Keep the original unique IDs (`device.id` for
covers and `device.id_attribute` for measurements); renamed defaults must not
replace user names, entity IDs, device IDs, or disabled registry preferences.

`async_setup` registers `velux_active.refresh` once. Each call validates a loaded
entry and awaits a shared entry-owned background task through the public
coordinator `async_refresh` API. Its result is captured per operation. Cancelling
one waiter leaves shared work running; successful entry unload cancels only
entry-owned work. The action stays registered and reports an error without a
loaded entry. A failed platform unload does not prematurely close resources;
Home Assistant reports `failed_unload`. No coordinator internals are copied.

Reauthentication and reconfiguration renew the password for the exact stored
login. Both flows validate credentials and fetch topology before saving. Do not
invent a cloud account ID, migrate entries, or accept an account switch without
a separately reviewed identity design. Config entries remain version 1 with the
original `username` and `password` data format.

## Test contracts and coverage

`tests/fixtures/legacy_v1.json` contains invented legacy entry and registry data.
The native upgrade test seeds it before setup and checks update, reload, and
reauthentication. The container lab additionally checks persisted custom names,
disabled entities, entry IDs, and all unique/entity IDs across a real HA restart.
Never derive these fixtures from a production export.

Run the commands in the README with `uv sync --locked`. The source suite uses the
pinned native Home Assistant pytest harness and a local synthetic HTTP service.
It covers auth/transient/malformed responses, token concurrency, account renewal,
manual-refresh cancellation, first-refresh failures, missing devices/data,
timestamps, and outage recovery. `scripts/check_coverage.py` requires 100% line
and branch coverage of `config_flow.py` and strictly more than 95% combined line
and branch coverage in **each** integration Python module, including `api.py`.
Missing files fail the gate. Do not add coverage exclusions to meet the gate.

The Docker lab checks the deterministic release archive through actual Home
Assistant REST/WebSocket APIs. It complements source coverage; its scenarios are
not added to the coverage percentage. Runtime networking remains isolated; any
explicitly authorized real-service smoke test runs separately and emits only
safe status/count summaries. Never print credentials, tokens, account/home/device
IDs or names, or raw cloud payloads from that check.

## Dependency and asset provenance

The cloud client source is public in
[`api.py`](custom_components/velux_active/api.py) under this repository's MIT
license. It follows the protocol references linked in the README. It imports
Python standard library code and Home Assistant-provided `aiohttp`; integration
code also uses Home Assistant and its `voluptuous` dependency. The empty manifest
`requirements` list means no additional installed runtime package, not a quality
rule exemption. `uv.lock` pins the development harness and Ruff and their
transitive dependencies. Simulator/test dependencies are never shipped as part
of the integration. Client extraction to a PyPI package and Core submission are
separate work.

Local brand assets use original, MIT-licensed community artwork. See
[asset provenance](assets/README.md) and `scripts/brand.py` for reproducible source.

## Supported versions and release procedure

The minimum supported Home Assistant release is **2026.9.3**. Validate **2026.9.3
and 2026.9.4**; later releases require another compatibility check. Inspect the
installed public HA APIs and current release announcements before changing
lifecycle behavior. Local brand images require HA 2026.3 or later, already covered
by this minimum.

1. Run locked source tests, the per-module coverage gate, and Ruff check/format.
2. Review all 30 local Bronze/Silver ledger rules and their evidence. Keep Custom
   status; do not set `manifest.quality_scale` to an official tier.
3. Run hassfest and HACS validation without ignoring brands.
4. Run `scripts/release.py build`, then `verify`. Prepare and test that exact ZIP
   on both target HA versions. Preserve the archive SHA-256 and sanitized receipts.
5. If authorized, run the separate read-only real-cloud smoke check. A simulated
   pass does not establish real-cloud access or rain freshness.
6. Update the manifest/project version together for a release, rebuild and retest
   if integration bytes changed, and publish through the release workflow. It
   builds the same deterministic ZIP and its file-hash manifest for HACS.
