# Core placement and admission proposal

This remains a Custom integration with its cloud client bundled in the HACS ZIP.
Core admission is a separate future project, not a custom-installation gate.

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
| Client ownership and license | Bundled same-repo client, MIT license, typed API and tests. |
| Public dependency | Not required for this custom integration. Agree an upstream-compatible library boundary before a future Core submission. |
| Protocol support | Strict HTTP regressions, both final installed targets and isolated frozen-wheel real-cloud proof passed owner validation. Registry corroboration is partial (9 known / 7 observed / 7 overlap / 2 missing / 0 extra); no provider completeness or compatibility guarantee is claimed. Formal review PASS at ba8def5 and owner acceptance close the locally achievable engineering scope; public distribution and Core admission remain separate deferred/external gates. |
| Domain and placement | Proposal above; upstream approval pending. Do not change custom-domain storage/unique IDs without a separately accepted migration. |
| Core manifest | Port under `homeassistant/components` only after placement acceptance; remove custom-only version/layout conventions and use approved documentation/requirements/ownership. |
| Official branding | Local custom assets have known provenance. Official brands repository contribution/admission is a separate upstream gate. |
| Native Core tests | Port synthetic protocol, flow, lifecycle, identity, discovery, privacy and dynamic topology tests to Core's native test harness and accepted fixtures. Custom pytest compatibility is not Core test admission. |
| Strict typing registration | Register the accepted Core domain in Core's `.strict-typing`; the local strict thirteen-module check does not edit or certify Core. |
| Website documentation | Prepare an upstream `home-assistant.io` integration page with setup, credential renewal, supported read-only models/functions, availability/update cadence, examples and limitations. Current README is source material, not an accepted website page. |
| Quality recognition | Local formal review passed; exact evidence is available for a future authorized submission. Official tier and Core inclusion require upstream acceptance, never a custom manifest claim. |

