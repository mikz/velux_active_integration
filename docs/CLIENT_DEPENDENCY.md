> Current scope: the user requires the client in `packages/velux-active-client`
> and has deferred publication, publisher/environment configuration and tags.
> This phase validates the exact local wheel with the integration ZIP. Any future
> publishing instructions below are preparation only, not authorized execution.
> The unpublished pin requires that matching wheel; the ZIP is not an ordinary
> standalone HACS installation. Public distribution and Core acceptance remain open.

# Client dependency decision and distribution gates

This is the M2b comparison checkpoint, dated 2026-10-01. The integration remains
Custom. No package version is claimed published or accepted by Home Assistant.

## Current reusable clients

[pyatmo 9.9.1](https://github.com/jabesq-org/pyatmo/releases/tag/v9.9.1)
ships VELUX NXG/NXO/NXS/NXD classes and `py.typed`. The downloaded public wheel
SHA-256 is `680fccaadd749e607150927495a9992bb45029901196d31fc498eadfcef61f36`.
Its [auth API](https://github.com/jabesq-org/pyatmo/blob/v9.9.1/src/pyatmo/auth.py)
accepts an injected aiohttp session, but `AbstractAsyncAuth` requires an external
access-token provider. It does not supply this integration's VELUX app
username/password and rotating-refresh protocol.

The [VELUX model](https://github.com/jabesq-org/pyatmo/blob/v9.9.1/src/pyatmo/modules/velux.py)
annotates rain as optional boolean. A bounded probe against the installed wheel
used the real `NXG.update_topology` parsing method: string `false`, empty list,
and integer zero were retained as string/list/int instead of rejected. Valid
boolean and null were retained. This does not prove every pyatmo entry point
accepts malformed data; it demonstrates that adopting its model does not supply
the strict rain boundary required here. The public request wrapper retries 429
up to four attempts and caps Retry-After at 60 seconds; it does not provide our
shared account-wide deadline and zero-request backoff contract.

[Niek's VELUX integration auth adapter](https://github.com/Niek/ha-velux-active/blob/1df8a2cfed070c40f81e453dff8c7a054459f9c0/custom_components/velux_active/api.py)
implements password/refresh against pyatmo's abstract auth, including fallback on
rejected refresh. It is integration source rather than a standalone distributed
strict client; its API and parsed snapshot retain broad `Any` data. Reusing that
adapter would still require ownership of auth, validation, serialization,
backoff, and the protocol regressions already tested here.

## Chosen path

Extract the existing tested read-only protocol into a separately versioned
package under `packages/velux-active-client` in this public repository. Keep the
current endpoint/auth semantics and regression cases; add strict validated
models rather than rewriting the protocol. This avoids introducing pyatmo's
broader control surface and request policy merely to duplicate the proven auth
adapter. The extraction must prove sparse status, rain, topology, rejected
refresh fallback, refresh rotation, injected-session ownership, cancellation,
and shared throttling through HTTP fixtures and cold installed artifacts.

The proposed distribution is **velux-active-client**, initial prepared version
**0.1.0**. PyPI metadata returned 404 for that name at this checkpoint; this is
not a reservation or proof of publication rights. The package needs its own MIT
license/source link/issues link, typed public API and `py.typed`, sdist/wheel,
versioned tag, scoped release workflow, clean install tests and exact integration
requirement pin. A wheel installed into a clean lab must satisfy the same HA
compatibility matrix before this gate is accepted.

The repository is public and the owner has GitHub push/admin access. Existing
GitHub repository secrets are empty; PyPI trusted-publisher configuration has
not been verified. After preparing exact reviewable metadata, artifacts and
workflow, publication requires an authorized PyPI project/pending publisher for
this distribution and repository workflow. Until actual distribution is
available, manifest installation and Core-ready publication remain open; do not
substitute a fabricated published version or source-only proof.

## Prepared publication contract

The standalone project is under `packages/velux-active-client`, with explicit
public exports, `py.typed`, MIT license and sdist/wheel build metadata. The
prepared release workflow is `.github/workflows/client-release.yml`; it accepts
only `client-v<exact package version>` tags and publishes only `dist/client` to
PyPI using the intended `pypi` environment and OIDC. The required trusted
publisher fields are owner `mikz`, repository `velux_active_integration`,
workflow `client-release.yml`, environment `pypi`, project `velux-active-client`.
Publisher configuration/access and environment protection have not been verified.
The metadata links to the actual public source repository; versioned package
source will be identified by the corresponding reviewed client Git tag.

For a future separately authorized publication, freeze and adversarially review the client before tagging/publishing 0.1.0. Publication remains deferred by the user; the current phase tests the local wheel only.
Use Git tags for public versioned client source; **do not create a client GitHub
Release**, which could become HACS latest. The existing integration release job
also excludes `client-v*` tags. Package publication does not authorize an
integration release, merge or production deployment. Never overwrite an already
published version with changed bytes; verify the downloaded published wheel
matches the reviewed hash before final packaged HA acceptance.
