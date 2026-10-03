# Limitee

Load leveling for every stack: a fast, Bottleneck-style job queue and rate
limiter for C#, TypeScript, Rust, Go, and Python.

> **Project status: design stage.** This repository currently contains the design
> specification only — there is no source code and no test suite yet. The
> documentation describes intended behavior and the portability contract that
> implementations must satisfy.

## Components

| Utility | What it does |
| --- | --- |
| **RateController** | Holds total in-flight work at or under a hard concurrency ceiling, pulling from a bounded queue as slots free |
| **GroupedRateController** | Per-group concurrency limits under one shared global ceiling |
| **ParallelWorkers** | Runs a recurring loop across a dynamically sampled number of workers |
| **AsyncAccumulator** | Accumulates inputs and invokes one batch function per batch, returning per-input outcomes |
| **WeightedAsyncAccumulator** | The same, budgeted by per-item weight instead of item count |
| **RetryDecorator** | Wraps a function with an attempt budget, backoff, predicates, and hooks |

Optional extras: cross-process coordination through a user-supplied Redis
adapter, and a separate opt-in OpenTelemetry package per language.

## Documentation

Start at **[docs/README.md](./docs/README.md)** — the documentation index and map.

| Document | Contents |
| --- | --- |
| [docs/architecture.md](./docs/architecture.md) | Component boundaries, invariants, composition, lifecycle, control-flow diagrams |
| [docs/design-principles.md](./docs/design-principles.md) | Simple defaults with advanced opt-in, functional conventions, policy vs mechanism |
| [docs/testing.md](./docs/testing.md) | The source of truth for test behavior, including the cross-language test matrix |
| [docs/decisions.md](./docs/decisions.md) | Consolidated decision log, with superseded, rejected, and unresolved items |
| [docs/utilities/](./docs/utilities/) | One focused design document per utility |
| [docs/subsystems/](./docs/subsystems/) | Queue and admission, Redis coordination, observability |

Contributors and coding agents should also read [CLAUDE.md](./CLAUDE.md) for the
working conventions.

## Design in one paragraph

Limitee limits by **concurrency**, not by time windows. Every queue is bounded,
and a queued job is never dropped unannounced. Defaults are safe and require
almost no configuration; every advanced behavior — scaling policy, retry
predicates, backoff, weights, group routing, the clock, the Redis client — is
injected as a function or an explicit option. Each language gets a full native
implementation with an idiomatic surface and identical observable behavior.

## License

See [LICENSE](./LICENSE).
