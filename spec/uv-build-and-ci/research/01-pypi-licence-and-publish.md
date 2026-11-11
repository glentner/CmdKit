# Research 01: PyPI licence metadata and the uv publish path

Sources were read on 2026-11-10 at `pypi/warehouse@main`, `pypa/packaging@main`,
`pypa/trove-classifiers` 2026.9.21.13, `astral-sh/uv` tag `0.13.7`, and `astral-sh/setup-uv`
v10.3.3. Licence-form behaviour was confirmed with a throwaway build under local uv 0.13.7.

## 1. Does PyPI reject `License-Expression` together with a `License ::` classifier?

**No.** Warehouse does not cross-check licence classifiers against `License-Expression`.

- `warehouse/forklift/metadata.py`, `_validate_metadata()`, has these classifier checks only:
  the classifier must be in `trove_classifiers.all_classifiers` (`"{c!r} is not a valid
  classifier."`), and it must not be in `deprecated_classifiers` (`"The classifier {c!r} has
  been deprecated…"`). `License :: OSI Approved :: Apache Software License` is valid and is
  not deprecated. Only five obscure `License ::` entries are deprecated in trove-classifiers
  2026.9.21.13.
  <https://github.com/pypi/warehouse/blob/main/warehouse/forklift/metadata.py>,
  <https://github.com/pypa/trove-classifiers/blob/main/src/trove_classifiers/__init__.py>
- The one licence rule that rejects uploads is that `License` and `License-Expression` are
  mutually exclusive:
  ```python
  if metadata.license and metadata.license_expression:
      errors.append(InvalidMetadata("license",
          "License is deprecated when License-Expression is present. "
          "Only License-Expression should be present."))
  ```
  It arrived with "Implement PEP 639, Metadata 2.4" (pypi/warehouse#16949, merged
  2024-11-13). It implements PEP 639's "PyPI MUST reject any that specify both `License` and
  `License-Expression`".
- `packaging.metadata` adds two more checks. It canonicalises and validates the SPDX
  expression (`licenses.canonicalize_license_expression`). It also requires each
  `License-File` path to be relative, contain no `..` and be already resolved (no `*`).
- PEP 639 leaves classifiers to the build tools: "If the `License-Expression` field is
  present, build tools MAY raise an error if one or more license classifiers is included…
  the presence of license classifiers SHOULD NOT raise an error unless `License-Expression`
  is also provided." <https://peps.python.org/pep-0639/#deprecate-license-classifiers>
- **uv_build 0.13.7 only warns.** `crates/uv-build-backend/src/metadata.rs` says "We don't
  produce a hard failure here, per PEP 639", with a `TODO: Produce a hard error here if the
  project also has structured license metadata`. The lab build printed:
  `warning: Found license classifier `License :: OSI Approved :: Apache Software License`.
  License classifiers are ambiguous and deprecated per PEP 639; projects should use
  `project.license` and `project.license-files` instead.`
  For comparison, setuptools ≥ 77 does hard-error on this combination. That is a build-side
  check, not a PyPI one.

## 2. Metadata 2.4, `License-File`, the legacy `License:` field, and uv_build's licence forms

**Warehouse:** `SUPPORTED_METADATA_VERSIONS = {"1.0", "1.1", "1.2", "2.1", "2.2", "2.3",
"2.4", "2.5"}`. `License-File` is accepted. `warehouse/forklift/legacy.py` checks that every
`License-File` exists, at `{name}-{version}.dist-info/licenses/{file}` in a wheel and under
the top-level directory in an sdist. A missing one is rejected with HTTP 400:
`"License-File {f} does not exist in distribution file {filename} at {path}"`. The legacy
`License:` field is accepted on its own; it is rejected only next to `License-Expression`.
Its length is not limited (`_LENGTH_LIMITS` covers only `summary`).

**uv_build 0.13.7** (`metadata.rs`, `License` is an untagged enum of `Spdx(String)`,
`Text{text}` and `File{file}`). Lab results:

| `pyproject.toml` | Metadata-Version | Licence fields | Licence file in wheel | In sdist |
|---|---|---|---|---|
| `license = "Apache-2.0"` + `license-files = ["LICENSE"]` | 2.4 | `License-Expression: Apache-2.0`, `License-File: LICENSE` | `dist-info/licenses/LICENSE` | yes |
| `license = "Apache-2.0"` (no `license-files`) | 2.4 | `License-Expression` only | **none** | **no** |
| `license = { text = "Apache-2.0" }` | 2.3 | `License: Apache-2.0` | **none** | no |
| `license = { file = "LICENSE" }` | 2.3 | `License:` holds the full file text | **none** | yes (legacy file) |
| `{ text = … }` + `license-files` | build fails | `When project.license-files is defined, project.license must be an SPDX expression string` | | |

So both table forms are accepted, but neither ships a licence file in the wheel. Wheels get
licence files only through `license-files` (docs: "The files referenced by
`project.license-files`, which are copied into the `.dist-info` directory").
<https://docs.astral.sh/uv/concepts/build-backend/>. uv_build has no default licence glob,
so a file must be listed explicitly; setuptools and hatchling do default one. A table-form
licence cannot be combined with `license-files`: uv raises the
`MixedLicenseGenerations` error.

## 3. `uv publish` with an API token

- Invocation: `uv publish` with `UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}` in the step
  `env`, or `--token`. `uv help publish` says "Using a token is equivalent to passing
  `__token__` as `--username` and the token as `--password`". The env var is preferred
  because it keeps the secret off the command line. The uv guide says the same:
  <https://docs.astral.sh/uv/guides/package/#publishing-your-package>.
- Trusted publishing defaults to `automatic` on GitHub Actions. In
  `crates/uv-publish/src/lib.rs`, `check_trusted_publishing()`:
  `TrustedPublishing::Automatic => { // If the user provided credentials, use those. if
  username.is_some() || password.is_some() || keyring… { return Ok(TrustedPublishResult::Skipped); }`.
  With a token set, uv does not attempt OIDC at all. Without credentials, an OIDC failure
  is `Ignored` (uv continues), so neither `id-token: write` nor a configured trusted
  publisher is needed. `--trusted-publishing always` combined with a token fails with
  `MixedCredentials`, so the flag should be left unset (or set to `never`).
- Default files: `[default: dist/*]`. uv "selects only wheels and source distributions and
  their attestations, while ignoring other files". It also uploads matching PEP 740
  attestations if present (`--no-attestations` turns that off).
- Default upload URL: `https://upload.pypi.org/legacy/`. `--check-url
  https://pypi.org/simple/` (or `UV_PUBLISH_CHECK_URL`) skips files that already exist, so
  a partial upload can be retried safely. The help text adds: "When uploading to PyPI,
  uploading the same file succeeds even without `--check-url`". It is optional on PyPI.
- `uv publish --dry-run` "checks the distribution metadata locally" without uploading. It is
  a useful CI gate.

## 4. `astral-sh/setup-uv`

- Latest release: **v10.3.3** (2026-10-28, commit `68559e99cc807c1eb7e9238fd43a15bba460eec2`).
  v10.0.0 came out on 2026-08-12.
- **There are no floating major tags any more.** The v8.0.0 release notes (2026-03-29)
  say: "No more major and minor tags… You won't be able to use `@v8` or `@v8.0`". The refs
  `v8`, `v9` and `v10` return 404; only `v7` and older remain. `uses:
  astral-sh/setup-uv@v10` therefore fails. Use `@v10.3.3`, or better the commit SHA with a
  `# v10.3.3` comment, as the README and uv's own docs do.
- v10 change: the default `enable-cache: auto` **disables caching on `release`,
  `pull_request_target` and `workflow_run` events** (cache-poisoning protection, setup-uv#984).
  The current publish workflow is triggered by `release`.
- Version pin: without `version`, setup-uv reads `required-version` from `uv.toml` or
  `pyproject.toml`, and otherwise installs the latest uv. uv's GitHub integration guide shows
  `version: "0.13.7"` under "Install a specific version of uv".
  <https://docs.astral.sh/uv/guides/integration/github/>. Pinning (or setting
  `[tool.uv] required-version`) keeps CI on the uv that was tested locally. The build itself
  is already bounded by `requires = ["uv_build>=0.13.7,<0.14"]`.

## Implications for the design

- Use the PEP 639 string form: `license = "Apache-2.0"` plus `license-files = ["LICENSE"]`.
  This is the only uv_build form that ships the licence in the wheel. It yields Metadata 2.4,
  which PyPI accepts and checks for file presence. Avoid the table forms: no licence in the
  wheel, and `{file=…}` puts the whole Apache text into `License:`.
- Drop the `License :: OSI Approved :: Apache Software License` classifier. PyPI would not
  reject it, but uv_build warns on every build, PEP 639 deprecates it, and it would break the
  build if the backend ever switched to setuptools ≥ 77.
- Publish step: `uv build` then `uv publish` with `env: UV_PUBLISH_TOKEN: ${{
  secrets.PYPI_TOKEN }}`. No `id-token` permission or `--trusted-publishing` flag is needed,
  because the token short-circuits automatic trusted publishing. Optionally add `--check-url
  https://pypi.org/simple/` for safe retries, and a `uv publish --dry-run` or `uvx twine
  check` gate before the upload.
- Pin `astral-sh/setup-uv` to an exact release or SHA (v10.3.3); `@v10` does not exist.
  Pin the uv `version` (or `required-version`) to the tested 0.13.x. Expect no uv cache on
  the `release`-triggered job.
