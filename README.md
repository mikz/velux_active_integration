# VELUX ACTIVE cloud sensors

The draft Platinum branch uses the separately versioned local project at
`packages/velux-active-client`. Its prepared 0.1.0 dependency is not published;
this branch is a development preview and is not a release-installable HACS
artifact. Development and isolated labs build/install the exact local wheel.
Publication is deferred by the owner. An integration release requires a
separately reviewed dependency distribution/installability gate; no production
deployment or package publication is performed by this work.

This Home Assistant integration reads VELUX ACTIVE account data, including the
cloud gateway's `is_raining` field. Sign in with the email address and password
used by the VELUX ACTIVE app.

It exposes gateway rain and status sensors, window and shutter positions, and
battery diagnostics. Covers report position only. The integration sends no
window, shutter, gateway, or rain-override commands.

## Install or update a released version

Requires Home Assistant **2026.9.3 or later**. The test lab covers 2026.9.3 and
2026.9.4.

1. Add [this repository](https://github.com/mikz/velux_active_integration) to HACS
   as a custom **Integration** repository.
2. Download **VELUX ACTIVE**, then restart Home Assistant.
3. Open **Settings > Devices & services**, select **Add integration**, and search
   for **VELUX ACTIVE**.
4. Enter your VELUX account email address and password.

For an existing installation, update the files and restart Home Assistant.
Keep the existing integration entry: account configuration, device identifiers,
and entity unique IDs are preserved. If you previously disabled the integration,
enable it after updating. The original rain sensor entity ID remains registered.

The **Reconfigure** action renews the password for the existing email address.
The form prefills that address and rejects another account. Home Assistant also
starts a reauthentication flow when VELUX rejects stored credentials. Failed
validation keeps the stored credentials. Temporary cloud outages and rate limits
trigger retries without asking for a new password.

Only one account can be configured. To switch accounts, remove the integration
first, then add it again. There is no verified stable cloud account ID for safe
account migration; switching accounts can change the device and entity identities.

To install manually, extract `velux_active.zip` into
`config/custom_components/velux_active/` and restart Home Assistant.

## Rain data and refresh

The integration polls status every 60 seconds and attempts account topology at
setup and every 300 seconds. Added devices appear without a reload, including
when the account previously had no devices or all existing entities were disabled. The `velux_active.refresh`
action waits for a completed status update. Concurrent calls share that update.
It takes no arguments and raises an error on cloud or authentication failure.
It remains registered after unload and raises a validation error when no account
is loaded. A Retry-After limit prevents manual calls from bypassing cloud backoff.
Decimal and HTTP-date Retry-After values retain their full deadline. The integration
conservatively shares this deadline across its clients in one Home Assistant process,
including setup retries, password validation, reload and account removal/re-add.
Trying another account inherits the remaining wait; a process restart clears this
in-memory state. This policy does not assert how the provider scopes its limits.
Unloading during a refresh cancels the entry-owned request and reports an error
to waiting callers.

The rain entity reports the gateway's cloud value. A missing measurement is
`unknown`; a failed poll or unreachable gateway makes the entity `unavailable`.
The integration does not substitute a missing measurement with “dry.” [VELUX documents that the app rain indication can take up to 15 minutes](https://www.velux.co.uk/support/wiki/active-rain-sensor).
This provider delay is distinct from our poll interval; this value alone does not establish
that a window is safe to open. Native VELUX rain protection remains on the device.

## Installation and configuration parameters

Before installation, set up a VELUX ACTIVE gateway and account in the VELUX ACTIVE
app. Home Assistant needs outbound HTTPS access to `app.velux-active.com`.
There is no local gateway address, port, callback URL, or OAuth registration to
configure.

| Parameter | Meaning |
| --- | --- |
| Email address | Required account login used by the VELUX ACTIVE app. Password renewal keeps this exact login. |
| Password | Required account password, masked in the form. Home Assistant stores it in the config entry; protect your configuration and backups. |

Status polling is fixed at 60 seconds and topology attempts at 300 seconds. There are no configurable polling,
control, or other options. Gateway, window, shutter, and switch data come from
cloud snapshots. A connectivity sensor remains available with state `off` when
the cloud successfully reports its device as unreachable. Other measurements
become unavailable for unreachable or absent devices or failed polls. Missing
measurements are unknown; numeric zero and boolean false remain valid values.
Successful later polls restore availability automatically.

Raw Wi-Fi strength, RF strength, and battery level are unitless diagnostics.
Their former dBm/mV labels lacked verified protocol support. Existing IDs, raw
values, saved preferences, and recorded history remain; future long-term statistics
stop for these three readings. A saved unit override stays stored but does not
convert a unitless reading. Battery percent remains a separate percent measurement.
Calibration is not labeled a fault, and silent mode is not labeled motor motion.

New registrations disable secondary diagnostics (raw signal/battery level, last
contact, gateway activity, and silent mode) by default. Rain, cover/position,
battery percent, and connectivity stay enabled. Existing enabled/disabled choices
and custom names survive updates. English and Czech entity/error translations are
included; other languages fall back to English.

Config-entry diagnostics export normalized health/counts and finite timing, not
provider names, IDs, credentials, tokens, or raw errors. Home Assistant supplies
its own system/manifest wrapper and entry-based filename; the integration controls
only its callback data. Device diagnostics are not provided. Authentication
failures use Home Assistant's existing entry-bound renewal notification; successful
renewal or entry removal cleans it up.

## Actions, triggers, and conditions

Use **Developer tools > Actions > VELUX ACTIVE: Refresh** to request cloud status,
or call it from an automation:

```yaml
action: velux_active.refresh
```

The action sends no device commands. There are no custom triggers or conditions.
Use Home Assistant's standard state triggers and state conditions with these
entities, such as triggering when the rain sensor changes to `on` or testing
whether connectivity is `off`. Select your registered entity ID in the UI.

## Remove

Open **Settings > Devices & services > VELUX ACTIVE**, select the entry's menu,
and choose **Delete**. This removes the account and its registered entities.
To remove the code as well, remove the repository download in HACS or delete
`config/custom_components/velux_active/`, then restart Home Assistant. The cloud
account and its physical devices stay configured in the VELUX app.

## Troubleshoot

- **Login rejected:** check the same account in the VELUX app, then complete the
  Home Assistant reauthentication flow or use **Reconfigure** to renew its password.
- **Cloud unavailable:** inspect Home Assistant logs and outbound HTTPS/DNS access.
  The coordinator logs each outage once and logs recovery once. Wait for automatic
  retry; repeated refresh calls cannot override a Retry-After limit.
- **Rain unknown:** the current cloud response omitted the measurement. Wait for
  a new cloud sample; unknown does not mean dry.
- **Device unavailable:** check the device and gateway in the VELUX app. A successful
  cloud poll can still report a disconnected device.
- **New device missing:** allow the next five-minute topology attempt. An outage
  can preserve old inventory while status succeeds; check the VELUX app and wait
  for recovery. Unsupported model IDs are retained for safe removal decisions
  but do not create entities.
- **Removed device still registered:** Home Assistant owns manual removal. Open
  its device menu after a fresh complete inventory no longer reports it. Removal
  is denied during stale, failed, partial or contradicted inventory. Devices are
  never automatically deleted; a reappearing device can register again.
- **Refresh rejected after unload:** reload or enable the account before calling
  the action. A failed unload follows Home Assistant's `failed_unload` state;
  restart Home Assistant to recover that framework state.

This remains a **Custom** community integration. The local
[quality ledger](custom_components/velux_active/quality_scale.yaml) tracks the
54 Bronze, Silver, Gold and Platinum engineering rules with named evidence and
open acceptance gates. It does not assign official Home Assistant certification.
The [acceptance matrix](docs/PLATINUM_ACCEPTANCE.md) separates locally tested work
from final artifact checks, user-deferred public distribution and Core acceptance.


## Supported devices and functions

The current parser recognizes these cloud records; this is not a guarantee for
all VELUX hardware or firmware revisions.

| Cloud model | Supported observations |
| --- | --- |
| NXG gateway | Rain, lock/movement/busy/calibration status, Wi-Fi strength and last-seen time when supplied. |
| NXO with `velux_type=window` | Read-only window position, reachability, silent state and reported firmware/last-seen time. |
| NXO with `velux_type=shutter` | Read-only shutter position and the same reported connectivity/status fields. |
| NXS / NXD | Reported battery and radio/connectivity diagnostics. |
| Other types | Inventory presence only; no entities are created. |

Available fields depend on the cloud snapshot. This integration has no open,
close, stop, set-position, rain-override or device configuration action. It does
not provide the local HomeKit connection or replace native VELUX protection.

## Use cases and automation examples

Use cloud observations to notify about reported rain, inspect window/shutter
positions, or identify missing battery/connectivity measurements. Handle rain
`unknown` and `unavailable` explicitly. Neither an `off` cloud state nor a recent
poll grants permission to open a window.

Replace the example entity ID with your registered rain entity. This notification
example reports rain and loss of evidence, and sends no physical commands:

```yaml
alias: VELUX cloud rain notification
triggers:
  - trigger: state
    entity_id: binary_sensor.example_gateway_is_raining
    to: "on"
  - trigger: state
    entity_id: binary_sensor.example_gateway_is_raining
    to: "unknown"
  - trigger: state
    entity_id: binary_sensor.example_gateway_is_raining
    to: "unavailable"
actions:
  - action: persistent_notification.create
    data:
      title: VELUX cloud rain status
      message: >-
        {% if is_state('binary_sensor.example_gateway_is_raining', 'on') %}
          The cloud gateway reports rain. Check the VELUX app and local conditions.
        {% elif is_state('binary_sensor.example_gateway_is_raining', 'unknown') %}
          The cloud response has no rain measurement. Rain status is unknown.
        {% else %}
          Rain status is unavailable. Check cloud connectivity and the gateway.
        {% endif %}
```

## Known limitations

The cloud API is unofficial and can change. One existing VELUX app account is
supported, with password renewal bound to that login. HomeKit-only setup does not
establish a cloud account. Status success does not certify cloud freshness or
successful topology discovery; a topology outage can leave accepted inventory
unchanged until a later five-minute attempt. See
[the topology contract](docs/TOPOLOGY_CONTRACT.md) for the account-inventory
inference and conservative manual-removal rules. Cloud measurements omit fields
on some devices; zero and false are valid, while missing/null rain is unknown.

## Develop and test

Install [uv](https://docs.astral.sh/uv/) and Python 3.14.2 or later in the 3.14
series. From this repository, install the locked test environment and run checks:

```sh
uv sync --locked
uv run python scripts/prepare_client_artifacts.py
uv run mypy --cache-dir=/dev/null
uv run pytest --cov=custom_components.velux_active --cov=velux_active_client --cov-branch --cov-report=json:artifacts/source-coverage.json
uv run python scripts/check_coverage.py artifacts/source-coverage.json
uv run ruff check .
uv run ruff format --check .
```

The tests reproduce early token refresh, broken unload, and stale rain
availability in the 2024 implementation. HTTP tests also exercise token rotation,
revocation, rate limits, sparse cloud responses, and HA login and reauthentication
flows. Tests use synthetic account data.

### Run the isolated Home Assistant lab

The lab follows [ha-operator's lab](https://github.com/mikz/ha-operator): separate
Home Assistant, simulator, and acceptance-runner containers on a private Docker
network. Docker Engine **29.4 or later** is required.

Build the release archive and prepare the images before starting the isolated
runtime:

```sh
uv run python scripts/prepare_client_artifacts.py
uv run python scripts/release.py build
uv run python scripts/lab.py prepare --ha-version 2026.9.4
uv run python scripts/lab.py test --ha-version 2026.9.4
```

Use `--ha-version 2026.9.3` for the other supported test target. Prepare versions
sequentially because the checkout shares synthetic TLS build inputs. Rebuild both
artifacts and prepare images again after editing installed integration/client bytes.
The local client wheel is preinstalled non-editably; the exact manifest pin and
installed member hashes are verified before native Home Assistant starts. The controller
rejects a stale archive or prepared image.

The simulator implements login, rotating tokens, home topology, and status over
HTTPS. Private Docker DNS resolves `app.velux-active.com` to the simulator, whose
certificate is trusted only in the disposable lab images. The integration
archive is identical to the release archive; it has no lab endpoint setting.

Before releasing startup gates, the controller verifies container membership,
mounts, DNS, and routing. Runtime containers have no external route, host network,
production credentials, or Docker socket. Dependencies download only during
preparation. The runner uses HA's native onboarding, config-flow, REST, and
WebSocket APIs. It checks rain changes, missing data, gateway disconnection,
cloud outages, throttling, token recovery, reload, restart, and reauthentication.

Each run writes sanitized results under `artifacts/lab/<run-id>/`. Results include
the HA/Python/dependency versions, ZIP and wheel digests, installed client member
hashes, isolation receipts, scenario outcomes and logs.
A passing lab proves behavior against the simulated protocol. It does not prove
that a particular real account can authenticate or that cloud rain data is fresh.

### Inspect a running lab

Add `--keep` to retain a passed lab:

```sh
uv run python scripts/lab.py test --ha-version 2026.9.4 --keep
uv run python scripts/lab_preview.py RUN_ID
```

Replace `RUN_ID` with the run ID printed by the test command. The preview prints
a loopback URL. Its relay connects only to that lab's Home Assistant, without
publishing a container port or adding an external route. The generated lab login
is in `.lab/runs/RUN_ID/control/preview-login.json`; keep this file local.

Stop the preview with Ctrl+C. To remove a retained lab and its private volumes:

```sh
uv run python scripts/lab.py clean RUN_ID
```

## Protocol references

The cloud client follows the bearer-token transport and `homesdata`/`homestatus`
endpoints used by [pyatmo](https://github.com/jabesq-org/pyatmo) and the VELUX login
parameters in [ha-velux-active](https://github.com/Niek/ha-velux-active).
The API is not a published VELUX compatibility guarantee. Retained failure logs
or a separately authorized account check are needed to establish the cause of a
particular production failure.
