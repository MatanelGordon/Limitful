# Use native package roots within each language workspace

**Status:** accepted

This decision supersedes ADR-0001. Each language keeps an expandable workspace,
but native import and package conventions take precedence over identical folder
names across languages.

C# projects are direct children of `csharp/` as refined by ADR-0002. TypeScript,
Rust, and Python keep the primary `limitful` package in `main/`, with future
packages as siblings. Go keeps the primary `limitful` package at the `go/` module
root so its import path is `github.com/MatanelGordon/Limitful/go`; future Go
packages use normal module subdirectories such as `go/opentelemetry/`.

## Constraints this creates

- Optional dependencies stay out of every primary package.
- TypeScript, Rust, and Python package workspaces discover direct siblings of
  `main/`.
- Go does not use a `main/` directory for the library because that directory name
  would become part of its public import path.
- Initial test tooling remains xUnit v3, Vitest, the built-in Rust and Go
  harnesses, and pytest.
- No documentation-site project is created until its framework is decided.
