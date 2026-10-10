# Plan: language package workspaces

**Status:** executing
**Created:** 2026-10-10   **Base branch:** master

## Goal

Prepare buildable, behavior-free development boilerplate for the five documented
Limitful language bindings. Each language root must be ready to grow into
multiple packages, and the root Makefile must provide one management surface.
Success is observable when every workspace restores, builds, and runs its empty
or scaffold-only checks through both native commands and the Makefile.

## Out of scope

- Implementing any Limitful API, runtime behavior, algorithm, or business test.
- Creating a documentation-site project or selecting its framework.
- Scaffolding optional OpenTelemetry, Redis synchronization, or framework adapter
  packages now.
- Publishing any empty package.

## Background

The repository currently contains only the design specification. The five
targets are C#, TypeScript, Rust, Go, and Python (`README.md`, `docs/README.md`,
and `docs/testing.md`). Commit `b7d4bb5` is the current documentation baseline.
The user's package-topology decision is recorded in ADR-0001: language roots are
expandable workspaces, with the main non-C# package under `<language>/main` and
C# projects sharing one solution.

The repository has no pre-existing `.memory/` or ADR constraints. Existing
documentation's “do not scaffold” note described the previous project state and
is superseded by this explicit user request; status wording will be updated
without changing the behavioral specification.

## Approach

Create the standard native workspace for each ecosystem, but keep entry points
empty and packages protected from accidental publication while they contain no
implementation. Language roots are disjoint and can be scaffolded concurrently.
After they merge, add the root Makefile, ignore/editor settings, and documentation
status updates centrally.

## Architecture

| Language | Workspace root | Primary package | Expansion model |
| --- | --- | --- | --- |
| C# | `csharp/Limitful.sln` | `src/Limitful.Core` | Future `Limitful.*` projects beside the core project |
| TypeScript | `typescript/` npm + Turborepo workspace | `main` (`limitful`) | Future npm workspaces beside `main` |
| Rust | `rust/Cargo.toml` | `main` (`limitful`) | Future workspace crates beside `main` |
| Go | `go/go.mod` | `main` (`package limitful`) | Future Go packages beside `main` |
| Python | `python/` uv workspace | `main` (`limitful`) | Future distributions beside `main` |

No implementation is shared across languages. The root Makefile delegates to
native tools and does not introduce a cross-language build system.

## File map

| Path | Change | Phase | Owner |
| --- | --- | --- | --- |
| `.adr/0001-language-package-workspaces.md` | new — durable package topology decision | 1 | root |
| `.plan/language-package-workspaces/plan.md` | new — reviewed execution plan | 1-3 | root |
| `.plan/language-package-workspaces/PROGRESS.md` | new — resumable orchestration state | 1-3 | root |
| `.plan/language-package-workspaces/prompts/**` | new — ori author and reviewer prompts | 1-3 | root |
| `.plan/language-package-workspaces/logs/**` | new — terse review outputs; transcripts ignored | 1-3 | root |
| `.plan/language-package-workspaces/agents/p2-dotnet-go.md` | new — agent status | 2 | p2-dotnet-go |
| `.plan/language-package-workspaces/agents/p2-typescript.md` | new — agent status | 2 | p2-typescript |
| `.plan/language-package-workspaces/agents/p2-rust-python.md` | new — agent status | 2 | p2-rust-python |
| `.plan/language-package-workspaces/handoffs/p2-dotnet-go.md` | new — bounded ori iteration handoff | 2 | p2-dotnet-go |
| `.plan/language-package-workspaces/handoffs/p2-typescript.md` | new — bounded ori iteration handoff | 2 | p2-typescript |
| `.plan/language-package-workspaces/handoffs/p2-rust-python.md` | new — bounded ori iteration handoff | 2 | p2-rust-python |
| `csharp/**` | new — solution, core project, and test project scaffold | 2 | p2-dotnet-go |
| `go/**` | new — Go module and behavior-free main package | 2 | p2-dotnet-go |
| `typescript/**` | new — nested Turborepo/npm workspace and main package | 2 | p2-typescript |
| `rust/**` | new — Cargo workspace and main crate | 2 | p2-rust-python |
| `python/**` | new — uv workspace and main distribution | 2 | p2-rust-python |
| `.gitignore` | new — generated artifacts for all five workspaces | 3 | root |
| `.editorconfig` | new — cross-language text defaults | 3 | root |
| `Makefile` | new — aggregate and per-language lifecycle targets | 3 | root |
| `README.md` | update — repository layout and scaffold status | 3 | root |
| `CLAUDE.md` | update — current scaffold status | 3 | root |
| `docs/README.md` | update — current scaffold status | 3 | root |
| `docs/testing.md` | update — implementation status and scaffold commands | 3 | root |

## Shared surface (phase 1 owns all of it)

ADR-0001 and this plan define directory ownership and package boundaries.
Language agents own only their assigned roots. Root integration files and all
existing documentation remain owned by the root agent.

## Phases

### Phase 1 — foundation

The root agent records ADR-0001, writes and reviews this plan, prepares disjoint
prompts, and commits the shared execution artifacts.

### Phase 2 — language scaffolds (3 agents)

- `p2-dotnet-go` — scaffold `csharp/**` and `go/**`.
- `p2-typescript` — scaffold `typescript/**`.
- `p2-rust-python` — scaffold `rust/**` and `python/**`.

### Phase 3 — integration and review

The root agent merges each green worktree, creates root management/configuration
files, updates status documentation, and runs all native and Makefile checks.
Each ori-authored change is reviewed by a different model family before merge.
Because this change adds no runtime behavior or secrets surface, the review is a
combined correctness/scope/security pass rather than a separate security agent.

## Test strategy

### Critical-path tests

```bash
dotnet restore csharp/Limitful.sln
dotnet build csharp/Limitful.sln --configuration Release --no-restore
dotnet test csharp/Limitful.sln --configuration Release --no-build
npm --prefix typescript ci
npm --prefix typescript run build
npm --prefix typescript run test
npm --prefix typescript run lint
npm --prefix typescript run format:check
cargo fmt --manifest-path rust/Cargo.toml --all -- --check
cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets -- -D warnings
cargo test --manifest-path rust/Cargo.toml --workspace
cd go && go test ./... && go vet ./...
uv --directory python sync --all-packages
uv --directory python build --package limitful
uv --directory python run --package limitful ruff check main
uv --directory python run --package limitful ruff format --check main
uv --directory python run --package limitful pytest main/tests
make check
```

### Edge cases

| Case | Axis | Status |
| --- | --- | --- |
| A language package has no implementation yet | absence | covered — native build/test commands must still pass |
| A future optional package is added beside `main` | cardinality | covered — workspace membership patterns and directory layout support siblings |
| An empty package is accidentally published | failure | covered — scaffolds remain private/non-publishable at version `0.0.0` |
| Toolchain is missing locally | failure | covered — Makefile `doctor` reports required commands |
| Generated output pollutes git | scale | covered — root `.gitignore` covers each toolchain's artifacts |
| Documentation-site framework choice | absence | deliberately out of scope — `docs/site/` remains specification only |
| Runtime concurrency, timing, cancellation, and malformed input | behavior | deliberately out of scope — no library behavior is implemented |

### Coverage

Behavioral coverage is intentionally not applicable because there is no library
behavior. Verification covers workspace discovery, dependency restoration,
compilation/package construction, empty test harness execution, linting, and
format checks for every scaffold.

## Definition of done

- Exactly five language roots exist: `csharp`, `typescript`, `rust`, `go`, and
  `python`.
- C# exposes `Limitful.Core`; every other primary package lives under `main` and
  is named `limitful` in its ecosystem.
- Future optional packages have an obvious sibling location without moving the
  core package.
- No Limitful runtime/API behavior or docs-site boilerplate exists.
- Native critical-path commands and `make check` pass.
- Final diff and cross-model review have no unresolved CRITICAL/HIGH findings.

## Risks and unknowns

- Go's required `main` directory yields an import path ending in `/main`, while
  the declared package name remains `limitful`; accepted because the user chose
  the cross-language `main` topology and Go consumers bind to the package name.
- Package publication names for future optional integrations are not decided;
  only their sibling boundaries are established now.
- The docs-site framework remains intentionally unknown and untouched.

## Decisions

- `ADR-0001` — Organize language bindings as expandable package workspaces —
  keeps optional dependencies outside the primary package.

## Amendments

- 2026-10-10 — Added one disjoint status file and one disjoint handoff file per
  ori agent so parallel progress and bounded-iteration state cannot collide.
