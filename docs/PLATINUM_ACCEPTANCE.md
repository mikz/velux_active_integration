# P2 rule acceptance matrix

There are 54 rules: 20 Bronze, 10 Silver, 21 Gold, 3 Platinum. Existing baseline evidence must survive P2; a row is not accepted until its gates and owner/adversarial review pass. No discovery exemption is assumed. Specific permitted exemptions require current primary-source evidence and review. Separate Core gates are in [the plan](PLATINUM_PLAN.md).

| Tier | Rule | Acceptance evidence / milestone | P2 state |
| --- | --- | --- | --- |
| Bronze | `action-setup` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `appropriate-polling` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `brands` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `common-modules` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `config-flow-test-coverage` | M2/M7 strict per-module branch gate, flow100%, HTTP/native failures and mutation-sensitive oracles. | Baseline evidence; revalidation pending |
| Bronze | `config-flow` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `dependency-transparency` | M2 strict types/session lifecycle; M2b proven distributed typed dependency; M7 package/API/type gates. | Baseline evidence; revalidation pending |
| Bronze | `docs-actions` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `docs-triggers` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `docs-conditions` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `docs-high-level-description` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `docs-installation-instructions` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `docs-removal-instructions` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Bronze | `entity-event-setup` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `entity-unique-id` | M0 R1 closure plus M3/M7 native migration/unknown/outage tests. | Open |
| Bronze | `has-entity-name` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Baseline evidence; revalidation pending |
| Bronze | `runtime-data` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `test-before-configure` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `test-before-setup` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Bronze | `unique-config-entry` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `action-exceptions` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `config-entry-unloading` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `docs-configuration-parameters` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Silver | `docs-installation-parameters` | M6 README section and installed/native examples; M7 evidence review. | Baseline evidence; revalidation pending |
| Silver | `entity-unavailable` | M0 R1 closure plus M3/M7 native migration/unknown/outage tests. | Open |
| Silver | `integration-owner` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `log-when-unavailable` | M0 R1 closure plus M3/M7 native migration/unknown/outage tests. | Open |
| Silver | `parallel-updates` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `reauthentication-flow` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Baseline evidence; revalidation pending |
| Silver | `test-coverage` | M2/M7 strict per-module branch gate, flow100%, HTTP/native failures and mutation-sensitive oracles. | Baseline evidence; revalidation pending |
| Gold | `devices` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `diagnostics` | M4 allowlist/sentinel privacy and native entry repair lifecycle; M7 installed HTTP proof. | Open |
| Gold | `discovery-update-info` | M1 bounded discovery research; M3 account-wide metadata; only documented rule-permitted exemption. | Open |
| Gold | `discovery` | M1 bounded discovery research; M3 account-wide metadata; only documented rule-permitted exemption. | Open |
| Gold | `docs-data-update` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-examples` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-known-limitations` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-supported-devices` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-supported-functions` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-troubleshooting` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `docs-use-cases` | M6 README section and installed/native examples; M7 evidence review. | Open |
| Gold | `dynamic-devices` | M3 complete atomic inventory, native additions/removal permission/reappearance, zero/disabled listeners and budgets; M7 both targets. | Open |
| Gold | `entity-category` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `entity-device-class` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `entity-disabled-by-default` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `entity-translations` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `exception-translations` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `icon-translations` | M5 typed descriptions, observed metadata, existing preferences, second-locale/fallback and installed/browser tests. | Open |
| Gold | `reconfiguration-flow` | Retain baseline native contracts; M2/M3/M5 changes and M7 lifecycle/account/action regression acceptance. | Open |
| Gold | `repair-issues` | M4 allowlist/sentinel privacy and native entry repair lifecycle; M7 installed HTTP proof. | Open |
| Gold | `stale-devices` | M3 complete atomic inventory, native additions/removal permission/reappearance, zero/disabled listeners and budgets; M7 both targets. | Open |
| Platinum | `async-dependency` | M2 strict types/session lifecycle; M2b proven distributed typed dependency; M7 package/API/type gates. | Open |
| Platinum | `inject-websession` | M2 strict types/session lifecycle; M2b proven distributed typed dependency; M7 package/API/type gates. | Open |
| Platinum | `strict-typing` | M2 strict types/session lifecycle; M2b proven distributed typed dependency; M7 package/API/type gates. | Open |

## Cross-rule acceptance gates

| Gate | Pass condition | State |
| --- | --- | --- |
| R1 boolean types | `test_invalid_wire_rain_fails_native_refresh_and_recovers`: HTTP/native action rejects seven malformed values including numeric 0/1; missing/null unknown and exact false/true recover. Owner independently reproduced all cases. | M0 passed; final artifact revalidation M7 |
| R1 identity oracle | `test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth` checks all 23 original registrations and live states; `test_legacy_identity_oracle_rejects_deliberate_rain_unique_id_mutation` proves a duplicate cannot satisfy the oracle. Lab seeds native version-1 storage before first candidate boot and checks reload, cold restart, reauth, then fresh login. | M0 candidate proof; final artifact revalidation M7 |
| R1 device logs | `test_device_disconnection_and_recovery_logs_are_deduplicated` and owner independent false/false/true/true probe prove one anonymous INFO transition pair. Omitted known devices need the M3 availability contract. | Explicit disconnection M0 passed; omission open M3 |
| R1 archive smoke | Frozen ZIP isolated origins and hashes, distributed dependency, no checkout fallback; safe real-cloud status/counts. | OPEN until M7 |
| Core-ready dependency | Public tagged/license/issues plus published typed distributions and exact installed HA pin. | External/engineering open M2b |
| Provider budget/completeness | Cadence caps and failure attempt timestamps, validated atomic account-wide IDs, conservative stale removal. | Open M3 |
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
