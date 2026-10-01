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

`packages/velux-active-client` owns the asynchronous cloud client; the integration's
`api.py` forwards its public API for compatibility. The client receives Home
Assistant's shared `aiohttp.ClientSession` and does not create or close it. The
client implements bounded HTTP requests, token rotation under an async lock,
read-only topology/status endpoints, and a monotonic Retry-After deadline.
The optional client `RateLimitState` contains only that deadline. A lazy typed
`HassKey` retains one conservative endpoint gate per HA process, including clients
created by a flow before component setup. Reconstruct credentials and sessions
normally; never retain them in the gate or reset it on unload/removal. Native HA
setup retries may run before the deadline: the new client must fail promptly with
zero HTTP requests. Decimal delays and UTC HTTP dates establish a full monotonic
deadline; concurrent shorter responses cannot shorten it. Parsing limits are 128
ASCII header characters and 18 decimal digits, with a 60-second fallback for
oversized or malformed input and a one-second minimum for zero/past dates.
These resource bounds are distinct from truncating an ordinary valid delay.
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
`legacy_storage.json` is generated before candidate setup using native registry
serializers. Regenerate it explicitly with
`uv run pytest scripts/generate_legacy_fixture.py -q`; the pinned pytest `hass`
fixture owns initialization and teardown. The lab seeds this storage before the
candidate's first boot, asserts the complete live inventory, and finishes with
a clean remove/re-add login path. Registry preservation checks must fail when
an original unique ID is deliberately changed, even if a duplicate works.

Run the commands in the README with `uv sync --locked`. The source suite uses the
pinned native Home Assistant pytest harness and a local synthetic HTTP service.
It covers auth/transient/malformed responses, token concurrency, account renewal,
manual-refresh cancellation, first-refresh failures, missing devices/data,
timestamps, and outage recovery. `scripts/check_coverage.py` requires 100% line
and branch coverage of `config_flow.py` and strictly more than 95% combined line
and branch coverage in **each** owned integration and client Python module.
Missing files fail the gate. Do not add coverage exclusions to meet the gate.

The Docker lab checks the deterministic release archive through actual Home
Assistant REST/WebSocket APIs. It complements source coverage; its scenarios are
not added to the coverage percentage. Runtime networking remains isolated. Any
explicitly authorized real-service smoke test runs separately and emits only
safe status/count summaries. Never print credentials, tokens, account/home/device
IDs or names, or raw cloud payloads from that check.

Prepare target versions sequentially in a shared checkout: preparation replaces
the shared synthetic TLS certificate before building all three images. Overlap
can mix certificates and fail TLS verification before integration setup.
An exclusive preparation lock rejects overlapping image builds.

## Dependency and asset provenance

The single cloud-client implementation is in
[`packages/velux-active-client`](packages/velux-active-client), under this
repository's MIT license. It follows the protocol references in
[the dependency assessment](docs/CLIENT_DEPENDENCY.md). Its runtime dependency is
`aiohttp`; integration code also uses Home Assistant and `voluptuous`. The manifest
pins the independently versioned client exactly. `uv.lock` pins development tools
and runtime dependencies for reproducible local validation.

This branch is a local validation candidate requiring the matching local client
wheel. Public distribution, publisher configuration, tags, and publication are
pending by user instruction. HACS does not install the sibling package folder;
green schema validation does not establish ordinary HACS installability. Do not
release the integration while its pinned client is unpublished.

Run `uv run python scripts/prepare_client_artifacts.py` before the source artifact
tests or lab preparation. This explicit network preparation builds the local
sdist/wheel and downloads hashed dependencies into an allowlisted wheelhouse.
Artifact tests then install non-editably into a fresh interpreter with no index
or checkout fallback. Lab images preinstall the same local wheel; the native
startup gate validates the exact manifest pin, installed origins, and member
hashes. Receipts bind both the integration ZIP and client wheel. Development's
workspace editable installation is not artifact acceptance evidence.

For final installed acceptance, generate the synthetic recorder seed before
preparation and run the two targets sequentially:

```sh
uv run pytest scripts/generate_legacy_recorder.py -q
uv run python scripts/release.py build
uv run python scripts/release.py verify
uv run python scripts/lab.py prepare --ha-version 2026.9.3
uv run python scripts/lab.py test --ha-version 2026.9.3 --timeout 900
uv run python scripts/lab.py prepare --ha-version 2026.9.4
uv run python scripts/lab.py test --ha-version 2026.9.4 --timeout 900 --keep
```

Freeze all source, prep, compose and runner bytes throughout these runs. Even a
harness-only compose change can invalidate an active controller's cleanup inputs.
The lab binds probe/preparation hashes separately from the ZIP/wheel. Logical
fixtures patch only the named candidate/client monotonic clocks. Exact-deadline
scenarios initialize through the shared native integer clock baseline. Assert
the intended endpoint request and inventory observation occurred before checking
their consequences: a quiet trace or denied removal alone does not prove an
inventory refresh happened. Fixtures use native service, flow, removal and
lifecycle boundaries; HA scheduling remains real.
Virtual backoff groups end with a full HA process restart, since the resource-free
deadline intentionally survives entry reload. Retention is incomplete cleanup;
after browser inspection, stop its separate loopback preview and use the scoped
`scripts/lab.py clean RUN_ID`, then record empty Docker-object verification.

The optional real-cloud runner `--compare-registry-stdin` accepts exactly
`{"known_registry_ids": ["..."]}` and prints `COMPARISON_INPUT_READY` before
reading. Supply private IDs through a pipe or a dedicated terminal with echo
disabled, never through files or command arguments. It forwards input to the
isolated child and emits only overlap/missing/extra counts, qualified inventory
shape booleans and anonymous gateway/rain counts before/after token refresh.
Missing/null rain is reported honestly and does not become dry or fail an otherwise
valid cloud observation. The existing credentials file remains separate.

Local brand assets use original, MIT-licensed community artwork. See
[asset provenance](assets/README.md) and `scripts/brand.py` for reproducible source.

## Supported versions and release procedure

The minimum supported Home Assistant release is **2026.9.3**. Validate **2026.9.3
and 2026.9.4**; later releases require another compatibility check. Inspect the
installed public HA APIs and current release announcements before changing
lifecycle behavior. Local brand images require HA 2026.3 or later, already covered
by this minimum.

1. Run locked source tests, the per-module coverage gate, and Ruff check/format.
2. Review all 54 local ledger rules and their exact evidence, including open gates. Keep Custom
   status; do not set `manifest.quality_scale` to an official tier.
3. Run hassfest and HACS validation without ignoring brands.
4. Check the payload inventory against the intended tracked integration files.
   The package contract includes visible Python (`.py`), JSON (`.json`), YAML
   (`.yaml`), and PNG (`.png`) files, including nested modules, translations, and
   brand assets. It excludes hidden files/directories, `__pycache__`, bytecode,
   and files with other suffixes, such as editor/runtime debris. Add and review
   new payload types explicitly. A builder and verifier sharing a broad glob can
   agree on shipping junk; their agreement alone does not prove a clean package.
   The source test compares package members with the tracked integration inventory
   independently and proves verification rejects extra archive members.
   Run `scripts/release.py build`, then `verify`. Prepare and test that exact ZIP
   on both target HA versions. Preserve the archive SHA-256 and sanitized receipts.
5. If authorized, run the separate read-only real-cloud smoke check. A simulated
   pass does not establish real-cloud access or rain freshness.
6. Update the manifest/project version together for a release, rebuild and retest
   if integration bytes changed, and publish through the release workflow. It
   builds the same deterministic ZIP and its file-hash manifest for HACS.

## Dynamic topology and removal evidence

See [the topology contract](docs/TOPOLOGY_CONTRACT.md) for the qualified inventory
inference, cadence and absence permission rules. Collect positive wire IDs before
model normalization: a malformed sibling or missing type can fail a status poll,
but must not erase credible device presence. Missing status is never inverse
presence evidence. Keep inventory failures separate from successful status and
never authorize deletion from a partly completed refresh. Log one anonymous
transition per device using effective measurement availability, including an
omitted device or unknown reachability; preserve native cloud outage logging.

## Metadata and diagnostic boundaries

Entity descriptions carry typed names, translation keys, classes and defaults.
Secondary diagnostics default off only for new registry records; updates never
rewrite user names, enabled/disabled choices, unit overrides or display precision.
Native HA can restore deleted registry records on remove/re-add, including their
preferences. Use never-before-seen device IDs to prove new-registration defaults;
use the restored records to prove preference preservation. In installed concurrent
service probes, child callers await only service completion. Put the native
block-until-done wait at the parent boundary, so children do not wait on their own
parent probe and mask otherwise completed refresh operations.
Raw Wi-Fi/RF/battery-level units were not verified: these remain exact unitless
numbers with the original IDs. Future long-term statistics stop for these three
fields; old dBm/mV metadata and samples stay untouched. The native recorder upgrade
test has a positive battery-percent compilation control, so an empty raw-field
result cannot pass merely because compilation did nothing. Await an unconditional
native recorder SynchronizeTask commit barrier; an empty queue may mean a worker
already popped the compilation task. Validate native statistics issues separately
through recorder/update_statistics_issues: preserved legacy metadata produces
state_class_removed and units_changed notices for the three corrected readings,
while valid battery percent and fresh installs produce none. Do not suppress
Core notices or delete/relabel historical metadata to hide them. Calibration is not a
fault indication and silent mode is not movement evidence.

Diagnostics are config-entry-only and allowlisted. Never export arbitrary provider
strings under a seemingly safe key: IDs, names, firmware text and raw errors can
contain secrets. Normalize known enums/counts and finite relative timings. The
callback owns its JSON only; HA owns enclosing system/manifest/issues metadata,
headers and the entry-based filename. Do not patch Core to claim broader privacy.
Native entry-bound reauth notifications supply the corrective account flow; no
second custom repair issue is needed. Test actual authenticated exports and native
repair cleanup, not only dictionary serialization.

Account-wide status must reject duplicate IDs across homes as well as within each
response. Presence is collected before normalization and remains a conservative
removal veto even when malformed siblings invalidate a snapshot. Request budgets
count incoming HTTP calls before rejection; accepted-token counts cannot prove a
throttled endpoint was never contacted.
