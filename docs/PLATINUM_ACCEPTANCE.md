# P2 rule acceptance matrix

There are 54 rules: 20 Bronze, 10 Silver, 21 Gold, 3 Platinum. Existing baseline evidence must survive P2; a row is not accepted until its gates and owner/adversarial review pass. Discovery is implemented. The cloud-only discovery-update-info exemption follows the reviewed current Core Sensibo precedent; no exemption closes publication or official recognition. Separate Core gates are in [the plan](PLATINUM_PLAN.md).

| Tier | Rule | Acceptance evidence / milestone | P2 state |
| --- | --- | --- | --- |
| Bronze | `action-setup` | async_setup owns registration; test_first_refresh_validates_setup_before_entities and test_action_is_registered_without_entry_and_survives_unload. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `appropriate-polling` | coordinator.py uses one-minute cloud polling and honors Retry-After; README Rain data and refresh, test_action_failure_backoff_and_automatic_recovery. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `brands` | Original MIT PNGs in brand/ with scripts/brand.py and assets/README.md; current HACS brands validator passes local tree, hassfest passes, packaged lab checks served icon bytes/MIME. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `common-modules` | coordinator.py owns polling; entity.py owns common snapshot identity and availability; test_entities.py. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `config-flow-test-coverage` | test_cloud.py and test_quality.py cover user, reauth, reconfigure and failure branches; check_coverage.py requires 100% lines and branches. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `config-flow` | Native UI user/password renewal flows in config_flow.py; test_native_user_flow_distinguishes_authentication_from_outage. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `dependency-transparency` | Public MIT packages/velux-active-client owns the protocol; exact manifest pin and local wheel provenance in CONTRIBUTING. Public distribution and ordinary HACS installation are user-deferred, not exemptions. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-actions` | README Actions, triggers, and conditions and Rain data and refresh describe zero-argument refresh, completed work and errors. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-triggers` | README Actions, triggers, and conditions states no custom triggers and explains standard entity state triggers. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-conditions` | README Actions, triggers, and conditions states no custom conditions and explains standard entity state conditions. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-high-level-description` | README introduction describes read-only VELUX cloud functionality and entity platforms. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-installation-instructions` | README Install or update contains HACS and manual installation steps and prerequisites. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `docs-removal-instructions` | README Remove describes entry, HACS/code removal and restart. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `entity-event-setup` | CoordinatorEntity supplies subscriptions in native lifecycle; test_failed_unload_preserves_resources_and_successful_unload_cancels_owned_work and native pytest cleanup checks. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `entity-unique-id` | test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth verifies complete live original inventory; test_legacy_identity_oracle_rejects_deliberate_rain_unique_id_mutation rejects a duplicate-ID regression. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `has-entity-name` | entity.py sets has_entity_name, entity-only measurement names and cover name=None; test_missing_devices_and_measurements_never_retain_previous_snapshot. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `runtime-data` | Typed VeluxActiveConfigEntry alias in coordinator.py is used in setup/unload/platform signatures; tests exercise entry.runtime_data. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `test-before-configure` | authenticate and get_home_data run before creating/updating entry; test_native_user_flow_distinguishes_authentication_from_outage and renewal failure tests. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `test-before-setup` | First coordinator refresh precedes entity setup; test_first_refresh_validates_setup_before_entities covers auth and transient failure. | Owner validated source and installed pair; final adversarial audit pending |
| Bronze | `unique-config-entry` | manifest single_config_entry uses HA-native enforcement; test_single_entry_rejects_duplicate_user_flow. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `action-exceptions` | test_action_failure_backoff_and_automatic_recovery, test_action_authentication_failure_starts_reauth, and unload/cancellation tests assert real errors. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `config-entry-unloading` | Native platform unloading, coordinator cleanup and entry-owned request cancellation; test_native_failed_unload_reports_framework_state_and_rejects_action and successful unload test. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `docs-configuration-parameters` | README Installation and configuration parameters lists credentials, fixed polling, password renewal and single-account limits. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `docs-installation-parameters` | README Installation and configuration parameters lists gateway/account, HA version and HTTPS prerequisites; no local address or OAuth registration. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `entity-unavailable` | test_invalid_wire_rain_fails_native_refresh_and_recovers and test_omitted_known_device_logs_one_outage_and_recovery cover malformed/missing/disconnected observations and recovery. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `integration-owner` | manifest codeowners includes @mikz and issue_tracker links this repository. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `log-when-unavailable` | test_unknown_reachability_uses_effective_availability_transition and omission tests prove one anonymous device transition pair; native coordinator cloud logging remains separate. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `parallel-updates` | PARALLEL_UPDATES=0 in all three read-only coordinator platforms; shared refresh test proves one concurrent cloud operation. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `reauthentication-flow` | test_account_renewal_rejects_switch_and_preserves_credentials_on_failures covers same-login renewal, invalid auth, transient failure and recovery for both renewal flows. | Owner validated source and installed pair; final adversarial audit pending |
| Silver | `test-coverage` | Locked source CI runs branch coverage over all integration modules and check_coverage.py requires each module above 95%; config_flow requires 100%. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `devices` | async_register_devices registers observed account devices and relationships; test_existing_device_home_move_keeps_original_live_entity preserves stable identity across home changes. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `diagnostics` | test_diagnostics_allowlist_omits_provider_credentials_names_and_errors and test_native_diagnostics_response_scopes_owned_data_and_export_metadata prove allowlisted data and scoped native export privacy; config-entry only. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `discovery-update-info` | Cloud transport uses a fixed endpoint; no discovered address is persisted or used. test_discovery_confirmation_login_failure_recovery_and_no_lan_account_binding verifies changed-address rediscovery. Current Core 2026.9.4 Sensibo quality ledger provides the same cloud-only exemption; see docs/DISCOVERY_EVIDENCE.md. | Exemption reviewed; owner validated installed no-LAN proof; final audit pending |
| Gold | `discovery` | test_discovery.py exercises exact raw TXT routing, paired/unpaired HomeKit coexistence, confirmation, account validation and simultaneous native flow completion; see docs/DISCOVERY_EVIDENCE.md. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-data-update` | README Data updates and availability documents separate 60-second status and 300-second topology attempts, failure retention and manual batches. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-examples` | README Examples provides a read-only notification automation with explicit unknown/unavailable handling. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-known-limitations` | README Known limitations documents cloud rain delay, read-only scope, single account, unsupported types and deferred distribution. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-supported-devices` | README Supported devices and functions lists NXG, NXO window/shutter and NXS/NXD plus unsupported inventory-only types. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-supported-functions` | README Supported devices and functions and Actions document read-only platforms and zero-argument refresh. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-troubleshooting` | README Troubleshooting covers account renewal, outages, rate limits, missing readings and safe diagnostic scope. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `docs-use-cases` | README Use cases describes notifications and observational history, never cloud-dry permission to open. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `dynamic-devices` | test_dynamic_device_addition_updates_registry_without_reload, test_empty_account_keeps_entry_discovery_listener and test_all_disabled_entities_keep_native_polling_and_discovery cover lifecycle and topology updates. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `entity-category` | test_new_diagnostic_defaults_and_useful_measurements verifies typed diagnostic categories without rewriting existing preferences. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `entity-device-class` | test_metadata.py verifies battery percent and the explicit unitless raw diagnostics correction; calibration and silent mode retain booleans without unsupported problem/running semantics. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `entity-disabled-by-default` | test_new_diagnostic_defaults_and_useful_measurements proves new secondary defaults; test_legacy_raw_diagnostics_keep_ids_options_and_historical_statistics preserves existing enablement/options. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `entity-translations` | test_native_published_entity_uses_locale_without_changing_identity verifies English/Czech/fallback names and stable unique IDs. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `exception-translations` | test_native_entity_and_exception_translation_with_fallback verifies exception catalogs; action/setup exceptions use native translation_domain/key. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `icon-translations` | icons.json supplies raw signal/battery, calibration and silent-mode icons where verified device classes do not apply; device-class icons remain native. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `reconfiguration-flow` | test_account_renewal_rejects_switch_and_preserves_credentials_on_failures verifies same-login password renewal, failure preservation and recovery. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `repair-issues` | test_native_reauth_repair_is_entry_bound_deduplicated_and_cleans_up uses native entry-bound corrective flow, successful renewal and removal cleanup; no duplicate custom issue. | Owner validated source and installed pair; final adversarial audit pending |
| Gold | `stale-devices` | test_manual_removal_requires_fresh_complete_uncontradicted_inventory plus native composite/child/removal/reappearance tests verify conservative permission; HA owns deletion. See docs/TOPOLOGY_CONTRACT.md. | Owner validated source and installed pair; final adversarial audit pending |
| Platinum | `async-dependency` | packages/velux-active-client is the sole typed async aiohttp protocol implementation; HTTP regressions and test_request_budget.py enforce bounded retries/rotation/global backoff. Public distribution is user-deferred. | Owner validated source and installed pair; final adversarial audit pending |
| Platinum | `inject-websession` | Client accepts an injected aiohttp session without closing it; HA supplies async_get_clientsession. Native unload and artifact smoke tests cover lifecycle; no runtime session factory or custom installer. | Owner validated source and installed pair; final adversarial audit pending |
| Platinum | `strict-typing` | Strict mypy checks every owned integration/client module with no blanket exclusions or Any leaks; tests/unit/test_typing.py verifies positive and negative typed consumers. | Owner validated source and installed pair; final adversarial audit pending |

## Current cross-rule acceptance gates

The owner has validated the frozen local candidate at `b2487c5c40f70dd1953a5e052f8e6c9a40d2e901`. Final acceptance by the persistent Astra/max reviewer is pending. The installed rule ledger remains frozen; these receipts are outside its payload.

| Gate | Current result and evidence |
| --- | --- |
| R1 boolean types | Owner validated strict HTTP/native invalid rain failure and valid/null recovery; both final installed targets replayed the boundary. |
| R1 identity oracle | Mutation-sensitive source oracle and true pre-candidate legacy setup, restart, reload and reauthentication passed on both final targets. This closes a weak oracle, not a proven historical identity migration regression. |
| R1 device logs | Explicit disconnection, omitted known devices and effective null reachability transitions passed source and installed scenarios without per-entity spam. |
| R1 archive smoke | Owner passed isolated real-cloud auth, topology, status, explicit token refresh and refreshed status using the exact final ZIP and local wheel. See `artifacts/m7-real-cloud-final-owner.json`. |
| Local dependency | Exact version 0.1.0 wheel installed non-editably; manifest pin, installed origins and all four client payload member hashes passed on both targets and real-cloud runner. |
| Public dependency / normal HACS installation | User-deferred. The candidate requires its matching unpublished local wheel. No publisher configuration, tags or publication are authorized. |
| Provider budget / inventory | Both installed targets passed raw multi-home cadence, overlap, auth and global backoff budgets and conservative absence/presence vetoes. Real VELUX returned explicit module arrays; historical registry comparison is PARTIAL: known 9 / observed 7 / overlap 7 / missing 2 / extra 0. Two absences remain unexplained; neither stale devices nor provider completeness is proved. |
| Final compatibility | Same local ZIP and wheel passed 25/25 scenarios on HA 2026.9.3 (`b0e29a16`) and 2026.9.4 (`0482ef9b`), including native privacy, localization, defaults, repairs, statistics history and cleanup. |
| Browser | Owner inspected the final 9.4 native integration, gateway and window pages. `artifacts/m7-browser-owner.json` binds the gateway screenshot and pair. Temporary preview and scoped Docker objects were removed. |
| Owner / adversarial acceptance | Repeated owner reproduction and final source/artifact/browser checks passed. Full persistent Astra/max audit remains pending; no official tier or Core admission is claimed. |

## Final evidence index

- Source: 256 tests + 37 subtests, strict mypy on all 13 owned modules, Ruff check/format, config-flow 100% line and branch coverage, and every integration/client module above 95% combined coverage. `artifacts/m7-source-coverage.json` records per-module results; minimum setup 95.92%, client 97.16%.
- Frozen ZIP: `8cdc546b6e85afe1931cb55ff29d68035fec8984f354a68a1dc320a59f86ccc7`, exactly 19 tracked integration members. Frozen local wheel: `e9d55df8e32d1127853119a35e09baccef8800526a6506a0143a28619069813a`, four client payload members.
- Local receipts: `artifacts/lab/velux-lab-2026-9-3-b0e29a16/acceptance.json` and `artifacts/lab/velux-lab-2026-9-4-0482ef9b/acceptance.json`. Both bind the same clean candidate revision and all 24 preparation hashes, including the local synthetic recorder database. Isolation and native cleanup passed; final 9.4 disposal is in `retention-cleanup.json` with empty containers/networks/volumes and removed preview login.
- Native statistics evidence preserves old samples, metadata, IDs and options; no new statistics for the three corrected raw fields. A committed battery-percent sample of 82 proves compilation works. Explicit native validation reports exactly six expected sensor notices: `state_class_removed` and `units_changed` for each legacy Wi-Fi, RF and battery-level ID. Battery percent and fresh installation have none. No warning suppression or history mutation occurs.
- Exact-head CI on b2487c5 passed all six checks: [Test 36804659899](https://github.com/mikz/velux_active_integration/actions/runs/36804659899), [Validate 36804659998](https://github.com/mikz/velux_active_integration/actions/runs/36804659998), [Lint 36804659929](https://github.com/mikz/velux_active_integration/actions/runs/36804659929). CI used merge revision `ede0d6f5f466b2f2ccde5eb7b4641ea83ac7e9cb`; 9.3 `cdd7b7f3` and 9.4 `fedd9d43` each passed 25/25 and isolation/cleanup. CI wheel wrapper hash is separately `256611e0e55b78753be9793ab19814b18096572e94d7d52d962f68bfbc2f85d8`; all four runtime members match the local wheel. CI-generated database hashes differ, while native history semantics and all 23 tracked harness sources match. CI does not claim the local binary wheel/database pair.
- Final cloud: `artifacts/m7-real-cloud-final-owner.json`, runner SHA `93796f001c2a6cab1211bc62c1f2f19953fd709f4874b56bd352869a1888adce`. One gateway has an available exact-boolean rain observation before and after token refresh; missing/null rain count is zero. Private comparison identifiers traveled only through echo-disabled child stdin, with no identifier-bearing files, arguments or output. Matching counts do not prove exact topology/status ID-set equality.
- Browser: `artifacts/m7-browser-owner.json` and hash-bound `artifacts/m7-browser-gateway-0482ef9b.png`. The integration remains Custom; user names/preferences and read-only controls were visible. Existing retained preview 18124 was untouched.

## Historical checkpoints (superseded by the current evidence above)

The following sections retain the evidence and limitations at the time of each checkpoint. Their pending states are historical and do not replace the current gate table.

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
