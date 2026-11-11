# Merge and installation gates

PR #22 restores the read-only VELUX cloud integration. The earlier accepted
runtime and real-cloud receipts are recorded in [the acceptance matrix](PLATINUM_ACCEPTANCE.md).
This page tracks the remaining installation gates as of 11 November 2026;
historical instructions and receipts in that matrix retain their original scope.

## Public client dependency

PyPI currently returns 404 for `velux-active-client`. Ordinary Home Assistant
installation cannot satisfy the manifest's exact `velux-active-client==0.1.0`
requirement. Installing a local wheel in the lab does not close this gate.

`python -m scripts.check_public_client` creates a fresh interpreter, downloads the
pinned wheel from PyPI without a cache or local source override, compares its
runtime members with tracked source, installs the manifest requirement with its
dependencies, and verifies the isolated installed version, origins and member
hashes. It writes `artifacts/public-client.json`. Both PR CI and the integration
release workflow require this check. A missing or changed package fails it.

The client publisher workflow publishes the same wheel and sdist used by the
tests; it no longer rebuilds them after validation. Before creating the client
tag, review the complete distribution metadata and file inventory.

The remaining publisher setup is:

| Field | Value |
| --- | --- |
| PyPI project | `velux-active-client` |
| GitHub owner | `mikz` |
| Repository | `velux_active_integration` |
| Workflow | `client-release.yml` |
| Environment | `pypi` |
| First client tag | `client-v0.1.0` |

The publisher has not been configured and publication is awaiting owner approval.
Do not create a client GitHub Release: client source tags are
separate from the integration releases consumed by HACS/Marketplace.

After publication, run the public-client gate and require all PR checks to pass
before marking the PR ready. Publication does not replace the existing isolated
runtime tests or establish new real-cloud freshness evidence.

## Home Assistant compatibility

The lab and CI matrix includes 2026.9.3, 2026.9.4 and the deployed 2026.11.1.
The new target must pass the same 25 installed scenarios, isolation checks and
scoped cleanup; adding it to the matrix alone is not acceptance evidence.

The November validation exposed two old timing assumptions in the harness:
scenarios must wait for Core `RUNNING`, and setup retry checks must allow Core to
honor the supplied `Retry-After`. The retry fixture now uses an eight-second
provider delay and waits for the actual second setup transition while holding
only the client clock inside that deadline. It still requires zero extra HTTP
requests, an unchanged shared deadline, and successful credential renewal at
expiry. Separate source cases retain the long-delay boundary checks. The source
request-budget fixture also uses an integer initial epoch for exact +300/+600
checks, matching the installed topology fixture's existing approach.
