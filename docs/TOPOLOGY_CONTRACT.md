# Account inventory and manual removal

The client requests VELUX `homesdata` without a home/device filter. We interpret
that response as the account-visible inventory. This is a protocol inference,
not a VELUX guarantee that every possible account configuration is complete.
[Netatmo's community manager confirmed](https://helpcenter.netatmo.com/hc/en-us/community/posts/23896792864658-API-homesdata-and-homestatus)
on January 16, 2025 that its related unfiltered endpoint returns all account
homes. The same thread documents nested status errors during an outage. Those
facts support the interpretation and error handling; they do not prove VELUX's
per-home module completeness. Owner final isolated frozen-artifact smoke
corroborated explicit module arrays in the VELUX response. Its private comparison
with historical HA registry IDs was partial: known 9 / observed 7 / overlap 7 /
missing 2 / extra 0. See the current evidence index in
[PLATINUM_ACCEPTANCE.md](PLATINUM_ACCEPTANCE.md) and the safe owner receipt
`artifacts/m7-real-cloud-correction-owner.json`. The two historical absences are
unexplained, not proven stale devices or cloud omissions. Matching counts do not
prove exact topology/status ID-set equality or provider completeness. No extra cloud requests or removal experiment were used to classify the two
absences; they remain unexplained.

An accepted inventory has an explicit homes array and an explicit modules array
for every home. All home IDs and account-wide module IDs must be nonempty strings
and unambiguous; every module must have a nonempty type, including unsupported
models. Explicit empty arrays are valid. Missing arrays, malformed records,
ambiguous duplicates and nonempty error/partial/pagination markers reject the
entire candidate. The client swaps its cache only after validation of all homes.
A failed attempt retains the accepted inventory and its observation time.

The coordinator polls status every 60 seconds. It attempts topology at setup and
no more than once per 300 seconds while running, including failed attempts. The
attempt clock is distinct from accepted-inventory and completed-status clocks.
A transient topology failure can coexist with successful status for known homes;
manual refresh completes that status operation successfully and the topology
health remains failed. Authentication and rate limits are shared terminal errors,
so neither endpoint can bypass them. Global 429 backoff blocks token calls too.
No extra request is made by a removal permission check.

Manual removal requires confident ownership by this loaded config entry, one
VELUX identity, a fresh accepted inventory (less than 300 seconds old), no newer
unresolved topology failure, no refresh in progress or failed status operation,
and absence from all inventory IDs. The permission hook never deletes anything;
Home Assistant owns removal and association cleanup. Other integrations' native
underlying devices remain intact.

Positive status presence vetoes inventory absence. The client collects every
valid string ID before model normalization and nested error classification,
including unsupported records and records beside malformed siblings. This veto
survives later missing/failed status until a later accepted inventory resolves it.
An omitted measurement or status record cannot prove device removal. Entities
look up current data by stable device ID across homes; a rename or home move
cannot change their identity. Entry-owned discovery listeners keep normal HA
polling active with zero entities or all entities disabled. Manual removal does
not create a permanent suppression list; a reappearing device can register again.

Named source evidence includes
`test_topology_replacement_is_atomic_and_requires_complete_identifiers`,
`test_partial_inventory_markers_reject_without_password_fallback`,
`test_topology_cadence_retains_inventory_on_failure_and_status_continues`,
`test_terminal_topology_failure_cannot_be_hidden_by_status_success`,
`test_existing_device_home_move_keeps_original_live_entity`,
`test_empty_account_keeps_entry_discovery_listener`,
`test_all_disabled_entities_keep_native_polling_and_discovery`,
`test_native_removal_preserves_other_owner_and_reappearance`,
`test_removal_is_denied_while_refresh_has_only_partial_observations`, and
`test_status_presence_veto_survives_malformed_siblings_and_nested_errors`.
Both final installed targets passed the topology/removal scenarios indexed in
PLATINUM_ACCEPTANCE.md. A later changed runtime pair must repeat these gates;
formal review PASS and owner acceptance cover the locally achievable scope.
