# VELUX ACTIVE cloud sensors

This Home Assistant integration reads VELUX ACTIVE account data, including the
cloud gateway's `is_raining` field. Sign in with the email address and password
used by the VELUX ACTIVE app.

It exposes gateway rain and status sensors, window and shutter positions, and
battery diagnostics. Covers report position only. The integration sends no
window, shutter, gateway, or rain-override commands.

## Install or update

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

The integration loads home topology at setup and polls status every minute.
Reload it after adding or removing devices in VELUX. The `velux_active.refresh`
action waits for a completed status update. Concurrent calls share that update.
It takes no arguments and raises an error on cloud or authentication failure.
It remains registered after unload and raises a validation error when no account
is loaded. A Retry-After limit prevents manual calls from bypassing cloud backoff.
Unloading during a refresh cancels the entry-owned request and reports an error
to waiting callers.

The rain entity reports the gateway's cloud value. A missing measurement is
`unknown`; a failed poll or unreachable gateway makes the entity `unavailable`.
The integration does not substitute a missing measurement with “dry.” Cloud
reporting can lag the physical sensor, so this value alone does not establish
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

The polling interval is fixed at one minute. There are no configurable polling,
control, or other options. Gateway, window, shutter, and switch data come from
cloud snapshots. A connectivity sensor remains available with state `off` when
the cloud successfully reports its device as unreachable. Other measurements
become unavailable for unreachable or absent devices or failed polls. Missing
measurements are unknown; numeric zero and boolean false remain valid values.
Successful later polls restore availability automatically.

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
- **New device missing:** reload the integration. Topology is loaded at setup;
  dynamic discovery and stale registry removal are outside this release.
- **Refresh rejected after unload:** reload or enable the account before calling
  the action. A failed unload follows Home Assistant's `failed_unload` state;
  restart Home Assistant to recover that framework state.

This remains a **Custom** community integration. The local
[quality ledger](custom_components/velux_active/quality_scale.yaml) tracks the
20 Bronze and 10 Silver engineering rules. It does not assign an official Home
Assistant certification. Full translations, diagnostics, dynamic discovery,
stale device cleanup, and an external client package remain separate work.

## Develop and test

Install [uv](https://docs.astral.sh/uv/) and Python 3.14.2 or later in the 3.14
series. From this repository, install the locked test environment and run checks:

```sh
uv sync --locked
uv run pytest --cov=custom_components.velux_active --cov-branch --cov-report=json:artifacts/source-coverage.json
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
uv run python scripts/release.py build
uv run python scripts/lab.py prepare --ha-version 2026.9.4
uv run python scripts/lab.py test --ha-version 2026.9.4
```

Use `--ha-version 2026.9.3` for the other supported test target. Rebuild the archive
and prepare images again after editing the integration or lab. The controller
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
the HA version, archive digest, isolation receipts, scenario outcomes, and logs.
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
