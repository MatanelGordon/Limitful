# CLAUDE.md

Operational guide for coding agents and contributors working on **Limitful** — a
fast, Bottleneck-style job queue and rate limiter, reimplemented natively in C#,
TypeScript, Rust, Go, and Python.

**The design lives in [docs/](./docs/README.md), not here.** This file is how to
work; those documents are what to build. When they disagree, the documents win —
and the disagreement is a bug in this file.

> **Status: design stage.** No language binding exists yet. There is no source
> code and no test suite to run. Do **not** scaffold empty language projects.

## Where things are

| You need | Read |
| --- | --- |
| The map of everything | [docs/README.md](./docs/README.md) |
| Component boundaries, invariants, composition, lifecycle | [docs/architecture.md](./docs/architecture.md) |
| Defaults philosophy, functional conventions, policy vs mechanism | [docs/design-principles.md](./docs/design-principles.md) |
| **Test behavior — the source of truth** | [docs/testing.md](./docs/testing.md) |
| Why something is the way it is, and what is still open | [docs/decisions.md](./docs/decisions.md) |
| **What every controller shares** — submission, `JobOptions`, admission queries | [docs/subsystems/controller-contract.md](./docs/subsystems/controller-contract.md) |
| RateController | [docs/utilities/rate-controller.md](./docs/utilities/rate-controller.md) |
| ThroughputController | [docs/utilities/throughput-controller.md](./docs/utilities/throughput-controller.md) |
| KeyedControllerRegistry *(draft — build this next)* | [docs/utilities/keyed-controller-registry-draft.md](./docs/utilities/keyed-controller-registry-draft.md) |
| GroupedRateController | [docs/utilities/grouped-rate-controller.md](./docs/utilities/grouped-rate-controller.md) |
| ParallelWorkers | [docs/utilities/parallel-workers.md](./docs/utilities/parallel-workers.md) |
| AsyncAccumulator | [docs/utilities/async-accumulator.md](./docs/utilities/async-accumulator.md) |
| WeightedAsyncAccumulator | [docs/utilities/weighted-async-accumulator.md](./docs/utilities/weighted-async-accumulator.md) |
| RetryDecorator | [docs/utilities/retry-decorator.md](./docs/utilities/retry-decorator.md) |
| AdaptiveCapacityPolicy — opt-in adaptation, outcome classification | [docs/utilities/adaptive-capacity-policy.md](./docs/utilities/adaptive-capacity-policy.md) |
| SynchronizationProvider — cross-instance coordination and capabilities | [docs/utilities/synchronization-provider.md](./docs/utilities/synchronization-provider.md) |
| Probe — periodic measurement with freshness metadata | [docs/utilities/probe.md](./docs/utilities/probe.md) |
| Queue, overflow, timeout stages, cancellation | [docs/subsystems/queue-and-admission.md](./docs/subsystems/queue-and-admission.md) |
| RedisSynchronizationProvider mechanics, liveness, outage behavior | [docs/subsystems/redis-coordination.md](./docs/subsystems/redis-coordination.md) |
| Events, metrics, the optional OTel package | [docs/subsystems/observability.md](./docs/subsystems/observability.md) |

`Q&A-Round-3.md` is the raw grooming transcript, kept for provenance. Its
decisions are consolidated in [docs/decisions.md](./docs/decisions.md); cite the
`D-nnn` record, not the transcript.

**Build order** is recorded in
[D-160](./docs/decisions.md#d-160-roadmap-order-keyed-registry-then-shared-job-options-then-supervision-then-outcome-classification):
`KeyedControllerRegistry` → shared `JobOptions` and deadline estimation → worker
supervision → outcome classification.

**Canonical name and coordination boundary.** The project and library are
`Limitful` ([D-162](./docs/decisions.md#d-162-limitful-is-the-canonical-project-and-library-name)).
Controllers depend on the backend-neutral
[`SynchronizationProvider`](./docs/utilities/synchronization-provider.md);
[`redis-coordination.md`](./docs/subsystems/redis-coordination.md) is the concrete
Redis provider's technical deep dive, not a competing public contract
([D-163](./docs/decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract),
[D-164](./docs/decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)).

## API philosophy

**Simple defaults and an easy first use; advanced behavior through explicit
options, properties, and function injection.**

- A first-time user supplies one value — the limit — and gets correct, safe
  behavior. Nothing else is required.
- **Every behavior and value has a default.** A knob with no defensible default is
  a design problem with the knob, not a reason to require it.
- **Defaults must stay safe, understandable, and ergonomic**, in that order. Safe
  means it cannot silently lose work or silently exceed a limit.
- **Never turn an advanced capability into required configuration.** Adding a
  predicate, a sampler, or a weight function must not be a precondition for the
  simple path, and must not change it.
- Advanced users reach deeper through properties and injected functions, never by
  subclassing or forking.
- Surfaces are idiomatic per language; **observable behavior is identical across
  all of them.** Only the surface differs.

## Coding conventions

Functional first, objects only where a lifetime must be owned and disposed.

- **Pure functions for decisions.** Predicates, samplers, weight functions, and
  backoff policies take context and return a value. They never mutate library
  state and may be called concurrently.
- **Immutable at the boundary, synchronized at the core.** Configuration objects,
  metrics snapshots, event payloads, and queued-item wrappers are values. Slot
  accounting and queue contents are mutable, small, explicitly locked, and never
  escape.
- **Explicit state transitions.** Model worker and job lifecycles as named states
  with enumerated transitions. A dead worker cannot be revived because no
  transition exists — not because a flag says so.
- **Small composable units.** Many small files, high cohesion: admission, slot
  accounting, worker loop, batching loop, timeout bookkeeping. 200–400 lines
  typical, 800 maximum.
- **Minimal hidden behavior.** No ambient singletons, no global registry, no
  background work before first use, no retry the caller did not ask for, no
  logging on the user's behalf. If something happens, either the caller asked or
  an event announces it.
- **Events over inheritance.** No binding requires deriving from a library base
  class.
- **Errors are never swallowed.** They reach the caller, an event, or both.
  Exhausted retries surface an **aggregated** error across all attempts.
- **Never infer severity from a generic failure.** The caller classifies outcomes
  — `Throttled`, `Overloaded`, `TransientFailure`, `CallerError` — and a bad user
  payload must never cause a service to throttle itself
  ([D-140](./docs/decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures)).
- **Never silently ignore an option you do not support.** Reject it at submission
  so a caller cannot build on a limit that is not being enforced
  ([D-116](./docs/decisions.md#d-116-weighted-concurrency-cost-for-ratecontroller-is-deferred)).
- **Never fabricate an estimate.** Return the absence type, or mark the value as
  statistical rather than computed
  ([D-114](./docs/decisions.md#d-114-estimatedstartat-is-best-effort-and-may-be-absent)).
- **Validate configuration at construction** with actionable messages.
- `Attempts`, never `Retries` — and it includes the initial execution.
- C# and Rust use functional constructs and current language features: records,
  immutable data, union-style results, exhaustive matching.

## Function injection and override points

Ship **mechanism**; inject **policy**. Anything that depends on the caller's
domain is a function they supply.

Controlled public override points — for advanced callers *and* for tests, which
is the same list on purpose:

**Time and scheduling** — clock, delay/scheduler, random source.
**Scaling** — worker-count sampler, sampling interval, max scaling delta,
min/max workers.
**Retry** — retry predicate, backoff policy, attempt hooks, priority mode.
**Admission** — overflow policy, queue capacity, the three timeout stages.
**Batching** — weight function, outcome correlation mode, batch bounds.
**Grouping** — group predicates, default-group policy, group priorities.
**Storage and coordination** — synchronization provider and scope; concrete
provider adapters, namespaces, liveness intervals, and degraded-mode policy.

Two rules:

1. **A test seam is a user seam.** If a test needs a hook users do not have, the
   hook is wrong. The clock is public API for exactly this reason.
2. **Justify new seams.** A new override point is warranted only when the library
   cannot pick a defensible default *and* the answer depends on the caller's
   domain. Seams are API surface forever.

## Hard invariants

Full list and rationale in
[docs/architecture.md § Invariants](./docs/architecture.md#invariants). Violating
one is never a local decision.

- A queued job is **never dropped unannounced**, and never by dropping the oldest.
- The only announced non-executions are cancel-pending shutdown, an expired
  queue-wait timeout, and cancellation of the job's own task.
- **Every queue is bounded.** Overflow rejects by default; waiting is opt-in.
- **`N` is the hard global in-flight ceiling.** A sampled worker count divides
  that budget and is clamped to it. A documented provider-specific degraded mode
  may weaken the coordinated guarantee only within its stated bound.
- **Cancellation is terminal** — never retried, never overridable by a predicate.
- **A retrying job holds no slot during backoff.**
- A timed-out or cancelled queued item **never executes later**.
- **Dead workers are never revived**; retiring workers finish their current task.
- A batch **never exceeds its max weight**, except one over-max item running alone
  in flexible mode.
- **A keyed registry never evicts a key with queued or in-flight work**, and
  reaching the key limit rejects the newcomer instead
  ([D-122](./docs/decisions.md#d-122-eviction-never-discards-live-work)).
- **Worker capacity is never silently lost** — every worker failure emits an event
  and either reduces the reported count or is replaced
  ([D-130](./docs/decisions.md#d-130-worker-failure-behavior-is-an-explicit-enumerated-supervision-policy)).
- **Adaptive behavior is never on by default**, and never raises a hard ceiling
  ([D-142](./docs/decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later)).
- **An insufficient synchronization provider fails configuration**, rather than
  silently weakening a guarantee
  ([D-150](./docs/decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration)).
- Distributed counting is **set-based**, never increment/decrement.
- A failing task is **isolated** to itself.

## Testing

[docs/testing.md](./docs/testing.md) is the source of truth for test behavior.

- **Full TDD.** Write the failing test for the case ID first, then implement, then
  refactor. Minimum 80% coverage per binding.
- **A behavioral contract change is a test change.** Update or add tests in
  **every implemented language binding** affected by that contract, in the same
  change. A binding left behind is a parity break, not a follow-up.
- **Keep semantics aligned through the shared test matrix.** Every business case
  has a stable ID (`RC-001`, `AA-001`, …) carried in a comment above each
  binding's test. Grep the ID to find every implementation.
- **Prefer deterministic tests.** Inject clocks, schedulers, random sources,
  storage adapters, and small configured limits. **No `sleep`, no real timers, no
  wall-clock assertions.** Gate concurrency with latches and assert the observed
  peak, not a sample.
- **Cover** defaults, every advanced override path, cancellation at each stage,
  all timeout stages, queue behavior, retries, grouped and global limits together,
  lifecycle/shutdown, and composition.
- **Do not invent bindings that do not exist.** Document intended portability;
  never create empty projects. When only one implementation exists, that is the
  only one to update.
- **A `Blocked` matrix row is never implemented by guessing.** Decide it in
  [docs/decisions.md](./docs/decisions.md) first.

## Changing design or API

1. **Check [docs/decisions.md](./docs/decisions.md) first** — it may already be
   decided, or deliberately open.
2. **Record the decision** as a new `D-nnn`. Mark what it replaces `Superseded`
   and link forward; never delete history.
3. **Update the one owning document** — each behavior has exactly one canonical
   home; everything else links to it.
4. **Update the test matrix**, then every affected binding.
5. **Do not change a public API to make documentation prettier.** If an API change
   is genuinely needed, propose it separately with its rationale.
6. Keep this file thin. New design detail belongs in `docs/`.

## Out of scope

Full list with reasoning in
[D-161](./docs/decisions.md#d-161-explicitly-out-of-scope): generic distributed job
queueing in the synchronization provider · adaptive behavior on by default ·
unbounded completed-job history · a built-in metrics database · exactly-once
execution promises for user functions · framework-specific APIs in core, which
ship as separate adapter packages instead.

Also out of scope: durable queues and job persistence across crashes or restarts
([D-072](./docs/decisions.md#d-072-job-persistence-across-restarts-is-out-of-scope)) ·
minimum job spacing · time-window or per-second rate limiting in `RateController`
([D-001](./docs/decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window)) ·
retries in `RateController`
([D-004](./docs/decisions.md#d-004-ratecontroller-never-retries)) ·
dynamic group creation
([D-060](./docs/decisions.md#d-060-groups-are-static)) ·
a shared Rust core with thin bindings
([D-100](./docs/decisions.md#d-100-native-reimplementation-per-language-no-shared-core)) ·
any OpenTelemetry or Redis-client dependency in core packages.
