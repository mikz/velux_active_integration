# Core placement and admission proposal

This branch remains a Custom integration and a local validation candidate that
requires its matching client wheel. The owner deferred public distribution,
publisher configuration, tags and publication. No Core PR, upstream messages,
release or official quality-tier request has been made.

## Proposed protocol boundary

Preserve `velux_active` for the VELUX app username/password cloud protocol and its
existing entry/entity identities while seeking upstream placement review.
[Core's Velux manifest at 2026.9.4](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/velux/manifest.json)
uses `pyvlx` and local polling for KLF gateways. This cloud account protocol should
not silently replace that transport or its installation requirements.
[Core's Netatmo manifest at the same tag](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/netatmo/manifest.json)
uses `pyatmo`, application credentials and webhook dependencies. Its
[config flow](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/netatmo/config_flow.py)
uses the native OAuth2 flow. Parsing VELUX device models in pyatmo does not establish
compatibility with the VELUX app password/refresh protocol. See the bounded
[client reuse assessment](CLIENT_DEPENDENCY.md).

The reviewable proposal is a separate cloud account integration using the proven
typed client, or an upstream-approved explicit VELUX authentication adapter within
the Netatmo family if that arrangement preserves these contracts. This choice
needs upstream acceptance; this repository does not decide Core namespace or
maintainer ownership. Keep read-only scope and stable account/device identities.
Document the unofficial endpoint, absence of a published VELUX API guarantee,
password-storage tradeoff, request budgets and failure classification. A discovery
hint establishes neither account ownership nor transport trust.

## Separate admission checklist

| Gate | Prepared evidence / remaining work |
| --- | --- |
| Client ownership and license | Standalone same-repo project, MIT license, typed public API, tests, sdist/wheel and scoped release workflow prepared. |
| Public dependency | User-deferred. Exact public immutable version and clean ordinary HA/HACS resolution must be verified before an installable integration release or Core submission. |
| Protocol support | Local HTTP regressions and prior source smoke exist. Final frozen-wheel real-cloud proof and safe inventory corroboration remain M7. No provider compatibility guarantee is claimed. |
| Domain and placement | Proposal above; upstream approval pending. Do not change custom-domain storage/unique IDs without a separately accepted migration. |
| Core manifest | Port under `homeassistant/components` only after placement acceptance; remove custom-only version/layout conventions and use approved documentation/requirements/ownership. |
| Official branding | Local custom assets have known provenance. Official brands repository contribution/admission is a separate upstream gate. |
| Native Core tests | Port synthetic protocol, flow, lifecycle, identity, discovery, privacy and dynamic topology tests to Core's native test harness and accepted fixtures. Custom pytest compatibility is not Core test admission. |
| Strict typing registration | Register the accepted Core domain in Core's `.strict-typing`; the local strict twelve-module check does not edit or certify Core. |
| Website documentation | Prepare an upstream `home-assistant.io` integration page with setup, credential renewal, supported read-only models/functions, availability/update cadence, examples and limitations. Current README is source material, not an accepted website page. |
| Quality recognition | Submit exact rule evidence after the locally achievable final audit. Official tier and Core inclusion require upstream acceptance, never a custom manifest claim. |

The future public workflow uses `client-v<version>` tags, not GitHub Release
objects, so client tags cannot promote an integration HACS artifact. Its intended
publishing environment and trusted-publisher configuration remain unconfigured
by user instruction. Changed published bytes must always receive a new version;
local unpublished candidate rebuilds do not imply a published release exists.
