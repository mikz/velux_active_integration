# Reviewed Platinum engineering plan P2

This document records the reviewer-approved plan (planning review R3: PASS), its
acceptance matrix, and open findings. The implementation baseline is
`d972da768892ec3e3afe02de97e06ba7c3c19e82` on `codex/velux-active-update`, continuing
[draft PR 22](https://github.com/mikz/velux_active_integration/pull/22).

This is a Custom integration. Completing 54 local engineering rules does not
award an official Home Assistant tier. Core submission and upstream acceptance
have separate gates below. No production deployment, entry enablement, actuator
command, integration release, or merge is authorized by this plan.

## Ownership and review

The sole implementation owner is the existing GPT-6.1 Sol/medium implementor.
The owner orchestrator is read-only and retains reproduction and acceptance.
`/root/platinum_reviewer` is the persistent Astra/max adversarial reviewer for
plan conformance and implementation, reused under the user's explicit direction.
Route labeled ambiguities with revision/evidence and a reply target through the
consult-advisor workflow. Do not create duplicate reviewers or parallel owners.
After each bounded milestone, report changed paths, performed checks, remaining
findings, and external gates. Repeat owner validation and adversarial review until
the gates pass. An engineering check cannot stand in for external publication or
upstream acceptance. Record evidence and receipts outside installed payload.

## Preserved contracts

- Keep the `velux_active` domain, version-one username/password entry format,
  exact account login binding, original entity unique IDs, custom names, disabled
  preferences, read-only covers, and zero-argument refresh action.
- Retain one-minute status polling, shared/injected HTTP session ownership,
  bounded timeouts, token rotation lock, global 429 backoff, native coordinator
  serialization, completed manual-refresh results, and entry-owned cancellation.
- Failed validation never saves credentials. Authentication failure starts native
  entry-bound reauthentication; transient failures and throttling never cause
  password fallback or duplicate repair issues.
- Unknown/null rain never means dry. Cloud-dry never grants permission to open a
  window. Cloud values and physical safety are distinct.
- Use MCP for real Home Assistant reads only. Preserve the retained loopback lab
  at port 18124. Work and acceptance use isolated labs with no external route.
- Fresh owner baseline on 2026-10-01: deployed/current stable HA 2026.9.4; production
  entry remains not loaded and disabled by its user. Target labs: 2026.9.3/2026.9.4.

## Reproduced review findings

| Finding | Observed gap | Required closure | Current state |
| --- | --- | --- | --- |
| R1-boolean | Lists/objects/empty strings coerce to dry; string `false` coerces to wet, and refresh succeeds. | Validate supplied booleans at the wire boundary; invalid data causes controlled API failure, unavailable entities and failed refresh; missing/null remain unknown; valid booleans and recovery work. | Open until M0 tests and owner validation. |
| R1-identity-oracle | Existing legacy test accepts a rain unique-ID mutation with an absent original live state and a duplicate. | Seed true legacy registry before first candidate setup; assert live original states/transitions, complete inventory and no duplicates across reload, cold restart and reauth; deliberate mutation must fail. | Weak oracle, not a proven identity migration regression. Open until M0/M7. |
| R1-device-logs | Reachable false/false/true changes availability without device outage/recovery logs. | Deduplicate per-device/service INFO transitions, retain native cloud logs, avoid per-entity spam. | Open until M0 native transition tests and owner validation. |
| R1-archive-smoke | Existing `.lab/real_cloud_check.py` imports checkout source. | Final frozen-ZIP isolated process, checked module origins/member/dependency hashes, no checkout fallback; only safe auth/topology/status/token-refresh counts/booleans. | SOURCE ONLY; stays open until final M7 archive smoke. M0 runner preparation cannot close it. |

## Milestones and acceptance

### M0: close reproduced gaps and prepare artifact smoke

Validate all supplied boolean measurements at normalization boundaries. Test
invalid list/object/string/number cases through real synthetic HTTP and native HA
setup/action/state paths; unknown/null and exact boolean false/true remain explicit. Numeric 0/1 supplied
as boolean measurements are malformed; numeric zero remains valid only for
proper numeric measurements.
Strengthen live identity and complete registry oracles with mutation-sensitive
negative tests. Registry data must exist before candidate setup, rather than
being renamed after candidate entities register. Add one device/service INFO
transition log per disconnection/recovery, including repeated states, multiple
entities, and no provider IDs/names in logs. Prepare an archive-only smoke runner;
use synthetic tests now and defer real-service closure to M7. No raw credentials,
responses, identifiers or exports may enter Git, CI or stdout.

### M1: audit all rules and discovery

Map all 20 Bronze, 10 Silver, 21 Gold and 3 Platinum rules to concrete implementation,
documentation and acceptance evidence. Only use exemptions permitted by the
specific current rule. Research cloud discovery capabilities and existing client
behavior; a fixed API endpoint alone is not proof of a discovery exemption.
Describe Custom engineering conformance separately from Core readiness and
upstream official recognition. Preserve provider documentation/source provenance.

### M2: strict ownership and typing

Strict mypy covers every owned integration and client module, typed config-entry
runtime, coordinator/entity generics, callbacks, DeviceInfo, and validated JSON
models. No blanket exclusion, ignore-missing-imports, or Any leakage. Add a
meaningful type-regression probe. Keep async I/O, injected aiohttp/httpx sessions
that the client never closes, bounded retry, token-refresh locking, global 429
backoff, and native serialization/cancellation. The inline strictly typed client
is an intermediate milestone, not the final Core-ready dependency.

### M2b: proven distributed client and Core proposal

**Owner steering, 2026-10-01:** keep the client in the local folder
`packages/velux-active-client`. Publication, publisher/environment configuration,
Git tags and releases are deferred by the user; do not ask again or perform them.
Complete all local engineering and adversarial gates using an independently
built, non-editably installed exact wheel. Final labs and real-cloud smoke freeze
and verify the same **ZIP + local wheel** pair with origin/member hashes, versions
and manifest pin satisfaction. No repository/PYTHONPATH/editable fallback, local
absolute manifest path, custom runtime installer or hidden public fallback.
Label the branch, PR and receipts as a local validation candidate requiring the
matching wheel. Ordinary HACS installation/public distribution/Core recognition
remain user-deferred gates; they are neither exemptions nor completed work.
The following public-distribution requirements remain the later Core-ready path.

Compare published external clients against current VELUX app username/password
auth, refresh rotation, rain, sparse status, topology, typing, session and retry
semantics. Leads include current pyatmo releases and ha-velux-active; do not decide
from old package knowledge. Adopt only demonstrated compatible code. Otherwise
extract the existing proven protocol without rewriting it into a separately
versioned public client package. Prepare concrete release work before reporting
missing publication access. Never manufacture a published version or contact
maintainers without authorization.

Required dependency evidence: public tagged source, license and issues; sdist and
wheel with `py.typed` and typed public API; release workflow; clean-install tests;
exact HA manifest version pin; protocol regressions; packaged HA compatibility
against the distributed dependency. Prepared code, published distributions and
upstream acceptance are distinct states. Continue independent engineering when
an external gate is unavailable. Record access gaps early.

Prepare a concrete Core placement/protocol-support proposal and checklist for
manifest/domain, official branding, native tests, `.strict-typing` registration,
and Home Assistant website docs. Only upstream acceptance closes official status.

### M3: dynamic, atomic account-wide topology

One coordinator lifecycle retains an entry-owned discovery listener even with
zero entities or all entities disabled. Initial cadence is status 60 seconds and
topology 300 seconds, pending provider budget validation. Setup fetches topology;
normal running makes at most one topology attempt per 300 seconds, including
failed attempts. Do not retry failed discovery every minute or add a separate
scheduler or arbitrary cooldown.

Replace inventory atomically only after complete validated home/ID/type data;
union all device IDs across the account, including unsupported models. Keep
separate inventory/status observation times. A transient or malformed topology
failure retains the previous accepted inventory and timestamp, records failure,
and permits independent successful status for known homes. Without prior valid
inventory, setup retries/fails. Terminal auth/429 is shared across endpoints and
cannot be bypassed. Manual refresh waits for a completed status operation and
attempts topology only when due. A non-auth/non-throttle discovery failure does
not itself fail successful manual status; expose/document the health distinction.

Budget assertions: topology <= one attempt/300 seconds plus setup; status one per
home/minute plus one per home/distinct accepted manual batch; overlapping manual
calls share one task; <= one 401 replay/request; one refresh plus one password
fallback only for rejected refresh, never transient/429; global 429 deadline
blocks every endpoint. Dynamic additions and metadata updates need no reload.
Home moves preserve IDs, entity/device names and registry preferences.

Manual stale removal only; never automatically delete. The hook grants permission
and HA owns registry deletion/association cleanup. Allow only confident ownership
by this entry and absence from initialized COMPLETE validated account-wide
inventory with no newer unresolved topology failure or stale/expired evidence.
Deny unknown ownership, incomplete/failure/uninitialized evidence or presence
anywhere, including unsupported models. If provider completeness is unprovable,
stay conservative. Test native UI/API on both HA targets, shared another-integration
association, remove/reappear, no permanent suppression, duplicate or resource leak.

### M4: diagnostics and native repairs

Initially expose config-entry diagnostics only. Explicitly allow normalized known
enums, counts, finite timing, versions and bounded anonymous relationships.
Arbitrary provider strings are unsafe even under an allowed key. Omit IDs, names,
location, credentials, tokens, raw exceptions and raw payloads. Sentinel tests
cover allowed fields and malformed nested content. Inspect native HTTP wrapper,
headers and filename; sanitize metadata owned by this export. Do not claim the
callback changes HA-generated metadata or edit HA Core. Verify native entry-bound
reauth repair creation, deduplication, corrective action, successful renewal and
removal cleanup. Add no duplicate custom repair/outage issues.

### M5: entity descriptions and localization

Verify classes, units and state classes. Use only observed device metadata and
relationships. Categorize diagnostics; noisy secondary sensors are disabled by
default only for new registrations. Existing enable/disable/name preferences
survive updates. Covers retain main-entity naming; rain/positions stay useful by
default. Translate entities/exceptions, ship English plus a second locale and
fallback tests; add icons.json only when device classes are insufficient. Preserve
IDs and statistics semantics. Prove results through installed-package/browser use.

### M6: user and developer documentation

Complete all seven Gold documentation rules: update behavior, examples, known
limitations, supported devices, supported functions, troubleshooting and use
cases. Explain read-only platforms, cadences and rain states. Notification
examples explicitly handle unknown/unavailable; never equate cloud-dry with
permission to open. CONTRIBUTING covers architecture, errors, identity, fixtures,
lab/privacy, typing, dependency provenance and releases. Authoritative VELUX
rain-indication delay documentation is a limitation, not proof of our freshness.

### M7: final frozen-artifact acceptance

Freeze installed code, dependency/version, translation and ledger bytes first.
Require 100% config-flow line/branch coverage, >95% combined line/branch coverage
in each owned integration/client module, strict mypy, Ruff, HACS, hassfest, and
meaningful R1/M3 regressions. Verify deterministic ZIP against an independent
tracked payload inventory; update the explicit asset/dependency payload contract
as needed. Record the final hash. Receipts stay outside installed payload; any
installed-byte change rebuilds and repeats affected artifact gates.

Run the same ZIP on both HA targets with true legacy bootstrap, reload/cold
restart/reauth, dynamic topology, stale-removal, diagnostics privacy, localization,
defaults, native repairs, unload and session/resource cleanup. Validate discovery
with zero entities/all disabled and adversarial budget/auth/throttle failures.
Refresh stable/deployed versions read-only before final compatibility reporting.

Final authorized real-cloud smoke extracts this frozen ZIP into an isolated
process with no source fallback, checks module origins/member hashes, and records
ZIP/dependency hashes and versions. Only safe boolean/count results of auth,
topology, status and token refresh leave the runner. Credentials and raw responses
never appear in CI, logs, Git or stdout. Prior source-only checks do not close this
gate. CI artifact uploads are narrow allowlists, never `.lab` or broad workspace.

## Separate Core readiness gates

| Gate | Required evidence | State at P2 start |
| --- | --- | --- |
| Public client distribution | Tagged public source/license/issues, published typed sdist/wheel, clean install/protocol tests, exact HA pin and installed dependency proof. | Open; inline source is not distribution. |
| Placement and protocol support | Concrete Core placement proposal plus compatibility/adoption evidence and provider support limitations. | Open; bounded current client comparison required. |
| Native Core integration | Correct domain/manifest/official branding, native Core tests, strict typing registration and HA website docs. | Open; custom equivalents do not imply Core admission. |
| Upstream acceptance | Maintainer review and accepted upstream changes. | External gate; never implied by local green checks. |

## Evidence tracking

The rule-by-rule acceptance matrix is [PLATINUM_ACCEPTANCE.md](PLATINUM_ACCEPTANCE.md).
The installed [quality ledger](../custom_components/velux_active/quality_scale.yaml)
records current truthful status. Link exact tests, package revisions and sanitized
receipts as milestones close. Final owner validation and adversarial review,
rather than this plan text, decide acceptance.
