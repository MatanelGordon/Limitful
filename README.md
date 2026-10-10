# Limitful

Load leveling for every stack: a fast, Bottleneck-style job queue and rate
limiter for C#, TypeScript, Rust, Go, and Python.

> **Project status: development scaffolds.** The five target-language workspaces
> are ready for development, but no Limitful behavior has been implemented yet.
> The documentation remains the portability contract that each implementation
> must satisfy.

## Components

| Utility | What it does |
| --- | --- |
| **RateController** | Holds total in-flight work at or under a hard concurrency ceiling, pulling from a bounded queue as slots free |
| **ThroughputController** | Applies caller-selected fixed-window, sliding-window, or token-bucket throughput limits |
| **GroupedRateController** | Per-group concurrency limits with an optional shared global ceiling |
| **ParallelWorkers** | Runs a recurring loop across a dynamically sampled number of workers |
| **AsyncAccumulator** | Accumulates inputs and invokes one batch function per batch, returning per-input outcomes |
| **WeightedAsyncAccumulator** | The same, budgeted by per-item weight instead of item count |
| **RetryDecorator** | Wraps a function with an attempt budget, backoff, predicates, and hooks |

Optional extras: cross-process coordination through a user-supplied Redis
adapter, and a separate opt-in OpenTelemetry package per language.

## Repository layout

Each language root is an expandable workspace. The primary package lives in
`main` except in C#, where the solution contains the `Limitful.Core` project.
Future packages such as OpenTelemetry or Redis synchronization belong beside the
primary package, not inside it.

| Language | Primary package | Workspace model | Test runner |
| --- | --- | --- | --- |
| C# | `csharp/src/Limitful.Core` | One solution, multiple projects | xUnit v3 |
| TypeScript | `typescript/main` | npm workspaces + Turborepo | Vitest |
| Rust | `rust/main` | Cargo workspace | Rust test harness |
| Go | `go/main` | Go module with sibling packages | `go test` |
| Python | `python/main` | uv workspace | pytest |

The scaffolds contain no library implementation and are marked private or
non-publishable where their ecosystem provides such metadata. The small Python
import test validates packaging only.

## Development

Run `make help` for the full command list. The common entry points are:

```sh
make doctor       # verify required toolchains
make setup        # restore/install every workspace
make check        # formatting, linting, builds, and tests
make test         # all five test runners
```

Every aggregate target also has a language-specific form, such as
`make test-csharp`, `make test-typescript`, or `make test-rust`.

## Documentation

Start at **[docs/README.md](./docs/README.md)** — the documentation index and map.

| Document | Contents |
| --- | --- |
| [docs/architecture.md](./docs/architecture.md) | Component boundaries, invariants, composition, lifecycle, control-flow diagrams |
| [docs/design-principles.md](./docs/design-principles.md) | Simple defaults with advanced opt-in, functional conventions, policy vs mechanism |
| [docs/testing.md](./docs/testing.md) | The source of truth for test behavior, including the cross-language test matrix |
| [docs/decisions.md](./docs/decisions.md) | Consolidated decision log, with superseded, rejected, and unresolved items |
| [docs/site/SPEC.md](./docs/site/SPEC.md) | Canonical documentation-site contract |
| [docs/utilities/](./docs/utilities/) | One focused design document per utility |
| [docs/subsystems/](./docs/subsystems/) | Queue and admission, Redis coordination, observability |

Contributors and coding agents should also read [CLAUDE.md](./CLAUDE.md) for the
working conventions.

## Design in one paragraph

`RateController` limits by **concurrency**, not by time windows.
`ThroughputController` separately limits starts over time through a
caller-selected fixed-window, sliding-window, or token-bucket strategy. Every
queue is bounded, and queued work is never dropped unannounced. Defaults are safe
and advanced behavior is explicit. Each language gets a full native
implementation with an idiomatic surface and identical observable behavior.

## License

See [LICENSE](./LICENSE).
