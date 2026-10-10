# Gate independent package publishing to the repository owner

**Status:** accepted

Each package is versioned independently. Release Please prepares reviewable
version and changelog pull requests, but a separate manual workflow is the only
path that creates a package tag or publishes. The workflow accepts one package,
requires the repository owner on the default branch, and uses registry trusted
publishing instead of long-lived registry tokens.

## Constraints this creates

- A release tag identifies the exact validated commit and is never moved.
- Registry publication requires the protected `publishing` environment.
- npm publication is staged for an interactive owner OTP approval; the OTP is
  never stored in GitHub.
- crates.io requires a separately confirmed one-time manual bootstrap release
  before its trusted publisher can be configured.
- Merging a release PR alone cannot publish, tag, or create a GitHub release.
