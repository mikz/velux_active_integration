# Contribute

Create a branch from `main`, add a regression case for the changed behavior,
and open a pull request. Use synthetic fixtures; do not commit account credentials,
tokens, device exports, or raw production logs.

Run the source checks and isolated Home Assistant lab described in the
[README](README.md). Integration changes must preserve existing entity unique IDs
and the username/password config-entry format. Test the exact release archive.
Keep the cloud simulator under `tests/lab`, outside the installed integration.

The lab controller, route validation, redaction, and preview relay were adapted
from [ha-operator](https://github.com/mikz/ha-operator) under the MIT license.
Contributions to this repository use the [MIT license](LICENSE).
