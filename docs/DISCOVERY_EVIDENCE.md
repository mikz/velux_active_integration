# Cloud account discovery evidence

The [Home Assistant discovery rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery/)
does not exempt an integration merely because its transport uses a fixed cloud
endpoint. VELUX documents [HomeKit-only setup](https://www.velux.com/homekit),
which must remain available alongside this optional cloud-account sign-in.

A [firsthand HomeKit service log](https://community.homey.app/t/app-pro-homekit-controller-for-a-better-homey/94520?page=27)
(post559, Finn_Nielsen2, 2026-01-22) identifies `_hap._tcp.local` with the exact
model `VELUX Gateway` followed by one terminal NUL. Only service/model values are
used here. Do not copy the log's personal network identifiers, addresses or
other properties into fixtures. Tests use invented identifiers and addresses.
The owner proved that native HA9.4 decoding retains the terminal NUL and that
canonical-only model matching fails; exact canonical and single-terminal-NUL
spellings match. The persistent reviewer accepted this bounded provenance.

Implement a native HomeKit discovery hint with explicit confirmation into the
existing account login. Accept only those two exact model spellings; never infer
an account identity from a HAP identifier, persist/contact a local host, or
submit credentials to the advertised address. Exact TXT matching is not proof
of authenticity or cloud account membership. Existing and disabled entries,
manual/discovery races and paired/unpaired HomeKit coexistence must be tested
through native raw-TXT routing on both target HA versions.

For `discovery-update-info`, the official
[HA2026.9.4 Sensibo Platinum ledger](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/sensibo/quality_scale.yaml#L70)
is a direct cloud-only precedent: discovery is done, while local-address updates
are exempt because cloud transport has no local network connection. The owner
and reviewer accepted this applicability. Before marking our row exempt, prove
native rediscovery with changed host/IP/port preserves stored account data and
cloud destination and produces no request to the advertised endpoint. Do not
invent a local-host setting just to update it. This exception does not confer
an official tier or upstream acceptance.
