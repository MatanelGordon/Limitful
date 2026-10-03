# Limitee Documentation

Limitee is a load-leveling toolkit: a bounded job queue, a concurrency-based rate
controller, parallel workers, batching accumulators, and a retry decorator —
reimplemented natively in C#, TypeScript, Rust, Go, and Python.

> **Project status: design stage.** This repository currently contains the design
> specification only. No language binding has been implemented yet, and no test
> suite exists. Every document below describes *intended* behavior and the
> portability contract that implementations must satisfy. Do not scaffold empty
> language projects to make the structure look complete — see
> [testing.md § Implementation status](./testing.md#implementation-status).

## Documentation map

| Document | What it owns |
| --- | --- |
| [architecture.md](./architecture.md) | Component boundaries, layering, global invariants, composition guidance, lifecycle and disposal rules, control-flow diagrams |
| [design-principles.md](./design-principles.md) | Simple defaults / advanced opt-in, functional conventions, immutability, policy vs mechanism, composability |
| [testing.md](./testing.md) | **Source of truth for test behavior**: strategy, test doubles, override points, deterministic time and concurrency, the cross-language test matrix |
| [decisions.md](./decisions.md) | Consolidated ADR-style decision log, including superseded, rejected, and unresolved items |

### Utilities

| Utility | Document | One-line responsibility |
| --- | --- | --- |
| RateController | [utilities/rate-controller.md](./utilities/rate-controller.md) | Hold total in-flight work at or under a hard concurrency ceiling `N` |
| AdaptiveCapacityPolicy | [utilities/adaptive-capacity-policy.md](./utilities/adaptive-capacity-policy.md) | Opt-in adaptation of effective controller capacity from observed conditions |
| SynchronizationProvider | [utilities/synchronization-provider.md](./utilities/synchronization-provider.md) | Optionally coordinate compatible utilities across service instances through interchangeable backend providers |
| GroupedRateController | [utilities/grouped-rate-controller.md](./utilities/grouped-rate-controller.md) | Per-group concurrency limits under one shared global ceiling |
| ParallelWorkers | [utilities/parallel-workers.md](./utilities/parallel-workers.md) | Run a recurring loop across a dynamically sampled number of workers |
| AsyncAccumulator | [utilities/async-accumulator.md](./utilities/async-accumulator.md) | Accumulate inputs and invoke one batch function per batch, returning per-input outcomes |
| WeightedAsyncAccumulator | [utilities/weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md) | AsyncAccumulator with per-item weights and a never-overshoot weight budget |
| RetryDecorator | [utilities/retry-decorator.md](./utilities/retry-decorator.md) | Wrap a function with attempt budget, backoff, predicates, and hooks |

### Cross-cutting subsystems

| Subsystem | Document | One-line responsibility |
| --- | --- | --- |
| Queue and admission | [subsystems/queue-and-admission.md](./subsystems/queue-and-admission.md) | The bounded-queue primitive shared by every utility: overflow policy, timeout stages, cancellation |
| Redis coordination | [subsystems/redis-coordination.md](./subsystems/redis-coordination.md) | Optional cross-process coordination: set-based counting, liveness, fail-open outage behavior, cluster slotting |
| Observability | [subsystems/observability.md](./subsystems/observability.md) | Raw event surface, metrics snapshots, and the optional OpenTelemetry package |

## Reading paths

**New contributor.** [architecture.md](./architecture.md) →
[design-principles.md](./design-principles.md) → the utility you are touching →
[testing.md](./testing.md).

**Coding agent.** [../CLAUDE.md](../CLAUDE.md) → the utility document for the
component in scope → [testing.md](./testing.md) for the affected test case IDs.

**Reviewing a behavioral change.** [decisions.md](./decisions.md) to find whether
the behavior was already decided → the utility document → the test matrix rows
that cover it.

**Implementing a new language binding.** [architecture.md](./architecture.md)
§ Implementation strategy → [design-principles.md](./design-principles.md)
→ every utility document → [testing.md](./testing.md) § Test matrix, which is the
checklist a binding must satisfy to be considered complete.

## How to change a documented behavior

Behavioral contracts are shared across five future bindings, so changing one is
a specification change, not an edit.

1. **Record the decision** in [decisions.md](./decisions.md). If it replaces an
   earlier decision, mark the old entry `Superseded` and link forward — never
   delete it.
2. **Update the owning document.** Each behavior has exactly one canonical home
   (the table above). Other documents link to it instead of restating it.
3. **Update the test matrix** in [testing.md](./testing.md): add, change, or
   retire case IDs. A behavioral contract without a case ID is not finished.
4. **Update every implemented binding** affected by the changed case IDs. Today
   that set is empty; it stops being empty the moment the first binding lands.
5. **Keep `CLAUDE.md` thin.** It points at these documents and states working
   conventions. New design detail belongs here, not there.

## Conventions used in these documents

- **`INV-n`** — a global invariant, defined in
  [architecture.md § Invariants](./architecture.md#invariants). Utility documents
  cite them rather than redefining them.
- **`D-nnn`** — a decision record in [decisions.md](./decisions.md).
- **`RC-001`, `AA-001`, …** — a business test case ID from
  [testing.md](./testing.md). Each binding's test carries its case ID in a
  comment.
- **Open item** — a deliberately unresolved detail. Open items are listed at the
  end of the document that will own the answer, and aggregated in
  [decisions.md § Unresolved](./decisions.md#unresolved-items).
- **Illustrative** — any code block in these documents is pseudocode for
  behavior. No public API signature is committed yet.
