# P2 rule acceptance matrix

There are 54 rules: 20 Bronze, 10 Silver, 21 Gold, 3 Platinum. Existing baseline evidence must survive P2; a row is not accepted until its gates and owner/adversarial review pass. Discovery is implemented. The cloud-only discovery-update-info exemption follows the reviewed current Core Sensibo precedent; no exemption closes publication or official recognition. Separate Core gates are in [the plan](PLATINUM_PLAN.md).

| Tier | Rule | Acceptance evidence / milestone | P2 state |
| --- | --- | --- | --- |
| Bronze | `action-setup` | async_setup owns registration; test_first_refresh_validates_setup_before_entities and test_action_is_registered_without_entry_and_survives_unload. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `appropriate-polling` | coordinator.py uses one-minute cloud polling and honors Retry-After; README Rain data and refresh, test_action_failure_backoff_and_automatic_recovery. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `brands` | Original MIT PNGs in brand/ with scripts/brand.py and assets/README.md; current HACS brands validator passes local tree, hassfest passes, packaged lab checks served icon bytes/MIME. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `common-modules` | coordinator.py owns polling; entity.py owns common snapshot identity and availability; test_entities.py. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `config-flow-test-coverage` | test_cloud.py and test_quality.py cover user, reauth, reconfigure and failure branches; check_coverage.py requires 100% lines and branches. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `config-flow` | Native UI user/password renewal flows in config_flow.py; test_native_user_flow_distinguishes_authentication_from_outage. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `dependency-transparency` | Public MIT packages/velux-active-client owns the protocol; exact manifest pin and local wheel provenance in CONTRIBUTING. Public distribution and ordinary HACS installation are user-deferred, not exemptions. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-actions` | README Actions, triggers, and conditions and Rain data and refresh describe zero-argument refresh, completed work and errors. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-triggers` | README Actions, triggers, and conditions states no custom triggers and explains standard entity state triggers. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-conditions` | README Actions, triggers, and conditions states no custom conditions and explains standard entity state conditions. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-high-level-description` | README introduction describes read-only VELUX cloud functionality and entity platforms. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-installation-instructions` | README Install or update contains HACS and manual installation steps and prerequisites. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `docs-removal-instructions` | README Remove describes entry, HACS/code removal and restart. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `entity-event-setup` | CoordinatorEntity supplies subscriptions in native lifecycle; test_failed_unload_preserves_resources_and_successful_unload_cancels_owned_work and native pytest cleanup checks. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `entity-unique-id` | test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth verifies complete live original inventory; test_legacy_identity_oracle_rejects_deliberate_rain_unique_id_mutation rejects a duplicate-ID regression. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `has-entity-name` | entity.py sets has_entity_name, entity-only measurement names and cover name=None; test_missing_devices_and_measurements_never_retain_previous_snapshot. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `runtime-data` | Typed VeluxActiveConfigEntry alias in coordinator.py is used in setup/unload/platform signatures; tests exercise entry.runtime_data. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `test-before-configure` | authenticate and get_home_data run before creating/updating entry; test_native_user_flow_distinguishes_authentication_from_outage and renewal failure tests. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `test-before-setup` | First coordinator refresh precedes entity setup; test_first_refresh_validates_setup_before_entities covers auth and transient failure. | Source validated; final installed/adversarial acceptance pending |
| Bronze | `unique-config-entry` | manifest single_config_entry uses HA-native enforcement; test_single_entry_rejects_duplicate_user_flow. | Source validated; final installed/adversarial acceptance pending |
| Silver | `action-exceptions` | test_action_failure_backoff_and_automatic_recovery, test_action_authentication_failure_starts_reauth, and unload/cancellation tests assert real errors. | Source validated; final installed/adversarial acceptance pending |
| Silver | `config-entry-unloading` | Native platform unloading, coordinator cleanup and entry-owned request cancellation; test_native_failed_unload_reports_framework_state_and_rejects_action and successful unload test. | Source validated; final installed/adversarial acceptance pending |
| Silver | `docs-configuration-parameters` | README Installation and configuration parameters lists credentials, fixed polling, password renewal and single-account limits. | Source validated; final installed/adversarial acceptance pending |
| Silver | `docs-installation-parameters` | README Installation and configuration parameters lists gateway/account, HA version and HTTPS prerequisites; no local address or OAuth registration. | Source validated; final installed/adversarial acceptance pending |
| Silver | `entity-unavailable` | test_invalid_wire_rain_fails_native_refresh_and_recovers and test_omitted_known_device_logs_one_outage_and_recovery cover malformed/missing/disconnected observations and recovery. | Source validated; final installed/adversarial acceptance pending |
| Silver | `integration-owner` | manifest codeowners includes @mikz and issue_tracker links this repository. | Source validated; final installed/adversarial acceptance pending |
| Silver | `log-when-unavailable` | test_unknown_reachability_uses_effective_availability_transition and omission tests prove one anonymous device transition pair; native coordinator cloud logging remains separate. | Source validated; final installed/adversarial acceptance pending |
| Silver | `parallel-updates` | PARALLEL_UPDATES=0 in all three read-only coordinator platforms; shared refresh test proves one concurrent cloud operation. | Source validated; final installed/adversarial acceptance pending |
| Silver | `reauthentication-flow` | test_account_renewal_rejects_switch_and_preserves_credentials_on_failures covers same-login renewal, invalid auth, transient failure and recovery for both renewal flows. | Source validated; final installed/adversarial acceptance pending |
| Silver | `test-coverage` | Locked source CI runs branch coverage over all integration modules and check_coverage.py requires each module above 95%; config_flow requires 100%. | Source validated; final installed/adversarial acceptance pending |
| Gold | `devices` | async_register_devices registers observed account devices and relationships; test_existing_device_home_move_keeps_original_live_entity preserves stable identity across home changes. | Source validated; final installed/adversarial acceptance pending |
| Gold | `diagnostics` | test_diagnostics_allowlist_omits_provider_credentials_names_and_errors and test_native_diagnostics_response_scopes_owned_data_and_export_metadata prove allowlisted data and scoped native export privacy; config-entry only. | Source validated; final installed/adversarial acceptance pending |
| Gold | `discovery-update-info` | Cloud transport uses a fixed endpoint; no discovered address is persisted or used. test_discovery_confirmation_login_failure_recovery_and_no_lan_account_binding verifies changed-address rediscovery. Current Core 2026.9.4 Sensibo quality ledger provides the same cloud-only exemption; see docs/DISCOVERY_EVIDENCE.md. | Exemption reviewed; installed no-LAN proof pending |
| Gold | `discovery` | test_discovery.py exercises exact raw TXT routing, paired/unpaired HomeKit coexistence, confirmation, account validation and simultaneous native flow completion; see docs/DISCOVERY_EVIDENCE.md. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-data-update` | README Data updates and availability documents separate 60-second status and 300-second topology attempts, failure retention and manual batches. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-examples` | README Examples provides a read-only notification automation with explicit unknown/unavailable handling. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-known-limitations` | README Known limitations documents cloud rain delay, read-only scope, single account, unsupported types and deferred distribution. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-supported-devices` | README Supported devices and functions lists NXG, NXO window/shutter and NXS/NXD plus unsupported inventory-only types. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-supported-functions` | README Supported devices and functions and Actions document read-only platforms and zero-argument refresh. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-troubleshooting` | README Troubleshooting covers account renewal, outages, rate limits, missing readings and safe diagnostic scope. | Source validated; final installed/adversarial acceptance pending |
| Gold | `docs-use-cases` | README Use cases describes notifications and observational history, never cloud-dry permission to open. | Source validated; final installed/adversarial acceptance pending |
| Gold | `dynamic-devices` | test_dynamic_device_addition_updates_registry_without_reload, test_empty_account_keeps_entry_discovery_listener and test_all_disabled_entities_keep_native_polling_and_discovery cover lifecycle and topology updates. | Source validated; final installed/adversarial acceptance pending |
| Gold | `entity-category` | test_new_diagnostic_defaults_and_useful_measurements verifies typed diagnostic categories without rewriting existing preferences. | Source validated; final installed/adversarial acceptance pending |
| Gold | `entity-device-class` | test_metadata.py verifies battery percent and the explicit unitless raw diagnostics correction; calibration and silent mode retain booleans without unsupported problem/running semantics. | Source validated; final installed/adversarial acceptance pending |
| Gold | `entity-disabled-by-default` | test_new_diagnostic_defaults_and_useful_measurements proves new secondary defaults; test_legacy_raw_diagnostics_keep_ids_options_and_historical_statistics preserves existing enablement/options. | Source validated; final installed/adversarial acceptance pending |
| Gold | `entity-translations` | test_native_published_entity_uses_locale_without_changing_identity verifies English/Czech/fallback names and stable unique IDs. | Source validated; final installed/adversarial acceptance pending |
| Gold | `exception-translations` | test_native_entity_and_exception_translation_with_fallback verifies exception catalogs; action/setup exceptions use native translation_domain/key. | Source validated; final installed/adversarial acceptance pending |
| Gold | `icon-translations` | icons.json supplies raw signal/battery, calibration and silent-mode icons where verified device classes do not apply; device-class icons remain native. | Source validated; final installed/adversarial acceptance pending |
| Gold | `reconfiguration-flow` | test_account_renewal_rejects_switch_and_preserves_credentials_on_failures verifies same-login password renewal, failure preservation and recovery. | Source validated; final installed/adversarial acceptance pending |
| Gold | `repair-issues` | test_native_reauth_repair_is_entry_bound_deduplicated_and_cleans_up uses native entry-bound corrective flow, successful renewal and removal cleanup; no duplicate custom issue. | Source validated; final installed/adversarial acceptance pending |
| Gold | `stale-devices` | test_manual_removal_requires_fresh_complete_uncontradicted_inventory plus native composite/child/removal/reappearance tests verify conservative permission; HA owns deletion. See docs/TOPOLOGY_CONTRACT.md. | Source validated; final installed/adversarial acceptance pending |
| Platinum | `async-dependency` | packages/velux-active-client is the sole typed async aiohttp protocol implementation; HTTP regressions and test_request_budget.py enforce bounded retries/rotation/global backoff. Public distribution is user-deferred. | Source validated; final installed/adversarial acceptance pending |
| Platinum | `inject-websession` | Client accepts an injected aiohttp session without closing it; HA supplies async_get_clientsession. Native unload and artifact smoke tests cover lifecycle; no runtime session factory or custom installer. | Source validated; final installed/adversarial acceptance pending |
| Platinum | `strict-typing` | Strict mypy checks every owned integration/client module with no blanket exclusions or Any leaks; tests/unit/test_typing.py verifies positive and negative typed consumers. | Source validated; final installed/adversarial acceptance pending |

## Cross-rule acceptance gates

| Gate | Pass condition | State |
| --- | --- | --- |
| R1 boolean types | `test_invalid_wire_rain_fails_native_refresh_and_recovers`: HTTP/native action rejects seven malformed values including numeric 0/1; missing/null unknown and exact false/true recover. Owner independently reproduced all cases. | M0 passed; final artifact revalidation M7 |
| R1 identity oracle | `test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth` checks all 23 original registrations and live states; `test_legacy_identity_oracle_rejects_deliberate_rain_unique_id_mutation` proves a duplicate cannot satisfy the oracle. Lab seeds native version-1 storage before first candidate boot and checks reload, cold restart, reauth, then fresh login. | M0 candidate proof; final artifact revalidation M7 |
| R1 device logs | `test_device_disconnection_and_recovery_logs_are_deduplicated` and owner independent false/false/true/true probe prove one anonymous INFO transition pair. Omitted known devices need the M3 availability contract. | Explicit disconnection M0 passed; omission open M3 |
| R1 archive smoke | Frozen ZIP isolated origins and hashes, distributed dependency, no checkout fallback; safe real-cloud status/counts. | OPEN until M7 |
| Local dependency | Same-repo client, typed wheel/sdist, fresh non-editable installation, exact manifest pin and ZIP/wheel origin/member proof. | Engineering open M2b/M7 |
| Core-ready public dependency | Public tagged/license/issues plus published typed distributions and ordinary HACS installation. | User-deferred; do not configure/tag/publish |
| Provider budget/completeness | [Topology contract](TOPOLOGY_CONTRACT.md): cadence caps, atomic explicit lists and positive-status veto source tests. | Source checkpoint; direct VELUX corroboration and M7 pending |
| Final compatibility | Identical tracked-payload ZIP on refreshed HA targets; native legacy/privacy/localization/default/repair/leak scenarios. | Open M7 |
| Owner/adversarial acceptance | Repeated owner checks and persistent Astra/max review, all findings closed or explicitly external. | Open |

M0 smoke preparation: `test_artifact_smoke_runs_isolated_zip_members_and_hides_credentials`
executes extracted module bytes in a Python isolated subprocess and verifies member
hashes. `test_smoke_empty_inventory_cannot_claim_status_proof` rejects a run that
cannot make a status request. These synthetic checks do not close the final real
cloud archive/dependency gate. The former smoke imported checkout source; that
finding remains open until M7.

M0 candidate checkpoint: source suite **119 tests + 37 subtests** passed;
the additional concurrent-preparation guard test passed separately. Ruff check
and format passed. Native maintenance generation passed with clean teardown.
Both HA targets passed **11/11** packaged lab scenarios with ZIP SHA-256
`6b8c736b08ac396a9c52d6df5a8ff749b0868ecdcfbbdc80176a554016aa47f5`:
9.3 receipt `velux-lab-2026-9-3-a9a1536c` and 9.4 receipt
`velux-lab-2026-9-4-a6e4734b`. Isolation and cleanup passed for both.
The earlier 9.3 receipt `velux-lab-2026-9-3-4c05b172` failed TLS setup because
two preparation phases mixed shared certificate inputs; the preparation lock
now rejects that overlap. It was not an integration compatibility failure.
Receipts remain outside installed payload. These are candidate checkpoint
results, not final Platinum/Core certification or M7 acceptance.

M2 inline-client checkpoint (before standalone extraction): locked mypy 2.3.1
strict mode passes all nine owned integration modules, with no blanket excludes,
ignored imports, or owned `Any` annotations. The external JSON decoder is cast
only to its recursive JSON value contract; collection/identity/measurement
validation narrows values before constructing explicit typed models. Native
ConfigEntry runtime, coordinator snapshots/manual outcomes, entity device types,
HA callbacks/device info and cover feature flags are typed.
`test_strict_types_accept_runtime_contract_and_reject_wrong_owner_and_device`
proves valid consumers pass and wrong runtime ownership/device arguments fail.
The source run passed **137 tests + 37 subtests**; the new type probe passed
separately. Config flow is **100%** and every module exceeds **95%** combined
line/branch coverage (minimum setup module96.43%; inline client97.31%).
`test_invalid_typed_measurements_reject_http_snapshot` and
`test_invalid_home_identity_rejects_http_topology` cover malformed HTTP data.
`test_invalid_token_lifetime_native_login_fails_safely_and_recovers` closes the
owner's infinite/NaN/unrepresentable token lifetime finding with native flow
recovery and no failed-login credential changes. Ruff check/format passed.
Strict mypy is now enforced in source CI. The M2b distributed dependency and
M3 protocol/topology gates remain open; installed source bytes have changed
since the M0 artifact receipt, which is only historical checkpoint evidence.

M2b local extraction checkpoint: the single implementation now lives in
`packages/velux-active-client`; the integration forwards its typed public API.
The independently versioned 0.1.0 wheel/sdist builds from the local project.
Strict mypy passes **12 modules**. Source tests passed **145 tests + 37 subtests**;
four additional tracked-wheel mutation controls passed separately (nine total
client-release tests). Ruff check/format passed. Config flow remains 100% and
all twelve owned modules exceed 95% combined coverage; client coverage is 97.31%.
The six isolated artifact-smoke tests pass, including editable/source and
mismatched-wheel negative controls, independently rerun by the owner.

Native HA 2026.9.4 receipt `velux-lab-2026-9-4-d98a6fc6` passed **11/11**
scenarios, isolation and cleanup with integration ZIP SHA-256
`3953cc8ad9bf2bb142c33abd50b013d1d35aa7f47ba644680a4db4101a4f83dd`
and client wheel SHA-256
`271fecffecfc03f67bb1cd0844e19c10f322aadaaf4cfa89145da7a2e560b20a`.
The native startup proof checks the exact manifest pin, non-editable installed
origins, all four client payload member hashes and runtime versions
(Python3.14.6, aiohttp3.14.3). This is bounded extraction compatibility evidence,
not the final M7 two-version/frozen-pair or real-cloud proof. Public distribution,
ordinary HACS installation and Core acceptance remain user-deferred; this local
candidate requires its matching wheel. No publisher configuration, tags or
publication occurred. M3 topology and remaining M1/M4–M7 gates remain open.


M3 source checkpoint: **193 tests** passed in the full branch-coverage run.
Strict mypy passes all twelve owned modules; Ruff check/format passed. Each module
exceeds 95% combined coverage: setup95.92%, coordinator98.65%, client97.41%,
config flow100%. These are source-level results, not installed pair acceptance.
[The topology contract](TOPOLOGY_CONTRACT.md) records the qualified account-scope
inference, independent clocks, cadence and manual-removal evidence.

The owner independently exposed two additional status-presence oracle gaps:
sparse IDs failed type normalization before tracking, and a malformed first
record stopped tracking later valid IDs. The final source collects all valid raw
IDs before normalization and nested errors; the veto survives subsequent omitted
status until later accepted inventory. The owner also found reachable=null became
available without a recovery log; logging now follows effective measurement
availability and tracks initial null reachability before omission. Named native
regressions cover all three cases. M3 owner/adversarial checkpoint review is
pending. Final M7 must replay these against the frozen installed wheel/ZIP, test
both HA versions and safely corroborate direct VELUX inventory shape/counts.

### M1/M4/M5 source checkpoint (final installed replay pending)

- Owner independently accepted M1 raw TXT routing/coexistence and native concurrent
  flow completion. `test_discovery.py` now also asserts simultaneous credential
  completion: one created account, one native ended-flow result, no remaining flows.
- Owner independently accepted M4 authenticated diagnostic privacy and native repair
  lifecycle. `test_diagnostics.py` covers supported NXD normalization as well as
  known models, unknown strings, finite clocks, export headers and wrapper boundary.
- `test_metadata.py` checks new-registration defaults, native English/Czech/fallback
  translation catalogs, and a recorder upgrade seeded before candidate first setup.
  The three raw diagnostics keep IDs/names/options (including V override and display
  precision), old samples/metadata; native compilation adds no converted/unitless
  replacement statistics. The original “creates no repair” checkpoint claim was
  incorrect: explicit native statistics validation reports state_class_removed
  and units_changed for each preserved legacy ID. These expected notices may
  remain visible while history is retained; fresh installs and valid battery
  percent have none. Tests assert the exact six warnings, not a blanket absence.
  No Core suppression, conversion, deletion or relabeling occurs. This is the
  explicit owner-approved M5 statistics amendment recorded in P2, not a claim of continuous future statistics.
- `test_request_budget.py` counts actual incoming multi-home HTTP calls, including
  rejected requests, and rejects account-wide contradictory duplicate status IDs.
  M7 must replay installed behavior against the frozen ZIP/wheel on both HA targets.

### Final source deadline checkpoint (installed pair pending)

The complete source run passed **248 tests + 37 subtests**. Strict mypy passed
all **13 owned modules**, Ruff check/format passed, and the branch-inclusive gate
passed each module (flow100%, client97.16%; minimum setup95.92%).
`artifacts/m7-source-coverage.json` is the local source receipt, outside the ZIP.

`test_api_errors.py` and `test_backoff_lifecycle.py` passed **82 HTTP/native cases**.
They retain ordinary Retry-After99999 and two-hour HTTP dates through exact
deadline recovery, preserve a longer deadline after an in-flight shorter response,
and bound malformed/oversized parsing without shortening ordinary valid values.
Native setup retries after six seconds reconstruct clients but send zero extra
HTTP requests; auth and topology initial limits share the lazy process gate.
Pre-component validation, blocked corrective flow, reload and removal/re-add
retain only the deadline, preserve stored credentials, and use fresh credentials
at expiry. The owner independently reproduced the original failures and exact
boundaries successfully against these stable source bytes. Installed replay,
final pair receipts and the full persistent Astra review remain pending.

### Frozen-candidate preparation checkpoint

The latest source run passes **250 tests + 37 subtests**, strict mypy on all
13 owned modules, Ruff check/format, and the per-module branch-inclusive gate.
The isolated artifact smoke has **8 cases**, including private stdin comparison
with matching/different inventories, identifier/credential output sentinels,
legitimate missing rain, and non-editable/wheel-origin negative controls.

Functional trial `364ac48c` completed **25/25 installed scenarios** on HA9.4,
with passed isolation. Its disposal failed after a concurrent harness compose
edit introduced a required environment variable absent from the older running
controller. Scoped cleanup subsequently verified empty containers/networks/volumes;
the failed trial and recovery evidence remain traceable in private staging.
This trial is **not final acceptance**. All source and harness bytes must remain
frozen across the final paired runs. Final frozen-pair receipts, real-cloud
comparison, browser inspection and the persistent Astra audit remain pending.
