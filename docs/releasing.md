# Releasing packages

Limitful versions and publishes each package independently. Release Please
prepares version/changelog pull requests; it never tags or publishes. The
manual **Publish one package** workflow validates, builds, tags, and publishes
exactly one selected package.

No current `0.0.0` scaffold can be published. The first real library change and
its release pull request must establish a non-placeholder version first.

## Release flow

1. Merge conventional commits for one package (`feat:`, `fix:`, and so on).
2. Review and merge that package's Release Please pull request. It updates only
   the package version, lock/version ledgers, and its `CHANGELOG.md`.
3. Open **Actions → Publish one package → Run workflow** on `master`. Select the
   package and run `dry-run` first.
4. Run it again with mode `publish` and confirmation `PUBLISH`. Approve the
   protected `publishing` environment when GitHub asks.
5. For npm, approve the staged package on npmjs.com with 2FA, then run the same
   package with `finalize-existing` and confirmation `PUBLISH`.

The mutating modes only accept runs started and rerun by `MatanelGordon`, from
the current `master` commit in `MatanelGordon/Limitful`. The checks run both
before and after environment approval. Registry authentication is OIDC-based;
no reusable publication token belongs in GitHub.

## Tags

The workflow creates a package-specific tag at the exact commit it built. It
will never replace or move a tag.

| Package selection | Registry | Tag |
| --- | --- | --- |
| `csharp/Limitful.Core` | NuGet | `csharp-core-v1.2.3` |
| `typescript/main` | npm | `typescript-limitful-v1.2.3` |
| `rust/main` | crates.io | `rust-limitful-v1.2.3` |
| `go` | Go module proxies | `go/v1.2.3` |
| `python/main` | PyPI | `python-limitful-v1.2.3` |

The GitHub release is created as a draft before a registry upload. NuGet, PyPI,
crates.io, and Go releases become final after publication succeeds. An npm
release stays draft until the staged version is approved with OTP and
`finalize-existing` confirms that the version is public.

## One-time GitHub setup

Before any mutating run:

1. In **Settings → Environments**, create `publishing`.
2. Add `MatanelGordon` as the sole required reviewer. Leave **Prevent self-review**
   disabled so the repository owner can approve their own deployment.
3. Restrict deployment branches to `master` and disable administrator bypass.
4. In **Settings → Actions → General**, allow GitHub Actions to create pull
   requests. Keep the repository token at its narrow default; each workflow job
   declares its own permissions.
5. Protect `master` so changes to the paths in `.github/CODEOWNERS` require owner
   review. Add tag rules for `csharp-core-v*`, `typescript-limitful-v*`,
   `rust-limitful-v*`, `python-limitful-v*`, and `go/v*` that prevent tag updates
   and deletion. Do not add a creation restriction that blocks this workflow's
   `GITHUB_TOKEN`.

Environment protection is an external GitHub setting and cannot be enforced by
the repository files. Do this before using `publish` or `finalize-existing`.

## npm

The workflow uses npm trusted publishing only for `npm stage publish`. It cannot
directly publish a version or approve a stage. Approval happens interactively on
npmjs.com and always requires your existing 2FA.

After the `limitful` package exists, open its **Settings → Trusted publishing**
and add:

- provider: GitHub Actions
- organization or user: `MatanelGordon`
- repository: `Limitful`
- workflow filename: `publish.yml`
- environment: `publishing`
- allowed action: stage publishing only; do not enable direct `npm publish`

Then set package publishing access to **Require two-factor authentication and
disallow tokens**. The checked-in `repository.url` must continue to identify
this GitHub repository exactly.

### First npm release

npm has no package settings page on which to configure a trusted publisher until
the name exists. For the first release only, merge the release PR, check out that
exact clean `master` commit, run the same local checks, and stage the generated
tarball from an interactive npm login:

```sh
mkdir -p .release-artifacts/npm
npm --prefix typescript ci
npm --prefix typescript run ci --workspace limitful
npm --prefix typescript pack --workspace limitful --ignore-scripts \
  --pack-destination ../.release-artifacts/npm
npm stage publish .release-artifacts/npm/limitful-*.tgz --access public
```

Inspect and approve it in npmjs.com's **Staged Packages** tab with OTP. Configure
the trusted publisher immediately afterward, disallow tokens, and run
`finalize-existing` to create the exact commit tag and GitHub release. Do not put
an npm token or OTP in GitHub Actions.

## PyPI

PyPI can bootstrap a new project without an API token through a pending trusted
publisher. On PyPI, create a pending publisher for project `limitful` with:

- PyPI project name: `limitful`
- GitHub owner: `MatanelGordon`
- repository: `Limitful`
- workflow: `publish.yml`
- environment: `publishing`

If the project already exists, add the same publisher under the project's
**Publishing** settings instead. The workflow's first successful upload turns a
pending publisher into the normal project publisher.

## NuGet

In the nuget.org account's **Trusted publishing** settings, create a GitHub
Actions policy for:

- GitHub owner: `MatanelGordon`
- repository: `Limitful`
- workflow file: `publish.yml`
- environment: `publishing`
- package scope: `Limitful.Core`

Create an environment variable named `NUGET_USER` in the GitHub `publishing`
environment. Its value is the nuget.org account profile name shown in the
account menu—not an email address and not a secret. A policy may initially show
as pending for a new package; the first matching publication activates it.

## crates.io

crates.io trusted publishing can only be configured after the crate exists. For
the first release, create the narrowest temporary crates.io token that permits a
new crate, merge the release PR, check out that exact clean `master` commit, and
run:

```sh
cargo publish --dry-run --locked --manifest-path rust/main/Cargo.toml
cargo login
cargo publish --locked --manifest-path rust/main/Cargo.toml
```

Immediately delete that token in **crates.io → Account Settings → API Tokens**.
CI cannot prove deletion without retaining the secret, so this is a required
human checklist item. Run `finalize-existing` to add the exact commit tag and
GitHub release.

Then open the crate's settings and add a GitHub trusted publisher for owner
`MatanelGordon`, repository `Limitful`, workflow `publish.yml`, and environment
`publishing`. Subsequent releases use short-lived OIDC credentials through the
workflow.

## Go

Go modules do not receive an uploaded artifact. The `go/vX.Y.Z` tag is the
publication, because this module lives in the repository's `go/` subdirectory.
The workflow tests the module, creates that exact tag, and finalizes the GitHub
release. A proxy can then discover the version from the tag.

## Recovery

- If an upload succeeded but GitHub release finalization failed, rerun the same
  package with `finalize-existing`. It requires the registry version and exact
  commit tag to agree.
- If npm is waiting for approval, approve or reject it on npmjs.com. Only use
  `finalize-existing` after the version is public.
- If upload failed before a version appeared in the registry, leave the draft
  untouched while investigating. Before retrying `publish`, remove that draft
  and its tag through the GitHub UI; the workflow deliberately refuses to reuse
  an existing publication tag.
- If a tag points anywhere other than the selected `master` commit, stop. The
  workflow will not move it; investigate the repository history and ruleset.

Package publication is irreversible in practice. Never use `--skip-existing`
or change a version merely to make a failed run green; first determine whether
the registry accepted the original artifact.

## References

- [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/)
- [npm staged publishing](https://docs.npmjs.com/staged-publishing/)
- [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPI pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [NuGet trusted publishing](https://learn.microsoft.com/nuget/nuget-org/trusted-publishing)
- [crates.io trusted publishing RFC](https://github.com/rust-lang/rfcs/blob/master/text/3691-trusted-publishing-cratesio.md)
- [Go module version numbering](https://go.dev/ref/mod#versions)
