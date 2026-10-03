# Decision Log

Durable design decisions for Limitee, consolidated from `CLAUDE.md` and the
round-3 design grooming Q&A (`Q&A-Round-3.md`). Each entry states what was
decided and what it costs. Superseded and rejected positions are preserved at the
bottom rather than deleted, because the reasoning is what stops them being
re-proposed.

**Consolidated:** 2026-10-03. **Status of the project:** design stage, no
implementation ([testing.md § Implementation status](./testing.md#implementation-status)).

**Status values.** `Accepted` — settled. `Accepted, with open items` — the
direction is settled but named details are not. `Superseded` / `Rejected` — see
[Superseded and rejected](#superseded-and-rejected).

- [RateController and the core ceiling](#ratecontroller-and-the-core-ceiling)
- [Retries](#retries)
- [ParallelWorkers](#parallelworkers)
- [Queue and admission](#queue-and-admission)
- [Accumulators](#accumulators)
- [Weighted batching](#weighted-batching)
- [Grouping](#grouping)
- [Lifecycle](#lifecycle)
- [Distributed coordination](#distributed-coordination)
- [Observability](#observability)
- [Project-wide](#project-wide)
- [Superseded and rejected](#superseded-and-rejected)
- [Unresolved items](#unresolved-items)

## RateController and the core ceiling

### D-001 RateController limits by concurrency, not by time window

**Status:** Accepted · **Source:** `CLAUDE.md` § RateController

**Context.** "Rate limiter" usually implies a time window, and the name invites
that reading.

**Decision.** `RateController` enforces its limit by **concurrency**: up to `N`
concurrent jobs in flight at any moment, pulling from the bounded queue as slots
free. It is not a fixed window, a sliding window, or a token bucket, and there is
no per-second cap. 1,000 jobs arriving in the first millisecond are processed at
whatever speed the concurrency configuration allows. Limitee implements a
deliberate subset of Bottleneck; minimum job spacing is not a goal.

**Consequences.** Burst smoothing is not available from this utility. A per-second
limiter would be entirely different logic and remains
[unresolved](#unresolved-items).

### D-002 N is the hard global in-flight ceiling

**Status:** Accepted · **Source:** Q&A Q2; `CLAUDE.md` § RateController

**Context.** `RateController` runs on `ParallelWorkers`, whose worker count is
sampled from a user function. If that count drove capacity, a sampler could
silently raise the limit.

**Decision.** During normal coordinated operation the configured `N` is the hard
global in-flight ceiling. The sampled worker count only **divides that fixed
budget** among workers; it must never increase total allowed in-flight work, and
any requested count is clamped to `N`.

**Consequences.** Enforcement lives in slot acquisition, never in trusting the
worker count. The single exception is fail-open Redis-outage behavior
([D-083](#d-083-a-redis-outage-fails-open-to-local-continuation)).

### D-003 Queues are always bounded

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § RateController, § Queues and Data Reliability

**Decision.** Every internal queue is bounded, with configuration for maximum
queued items, timeouts, and an overflow strategy. Unbounded growth causes serious
memory problems at larger scale, and worse when the service is stacked on
something more constrained.

**Open.** The default capacity value is not chosen.

### D-004 RateController never retries

**Status:** Accepted · **Source:** `CLAUDE.md` § RateController

**Decision.** `RateController` does not support retries at all. Retry logic lives
in the separate, composable [RetryDecorator](./utilities/retry-decorator.md).

**Consequences.** Users wanting retries compose two utilities, and the composition
order is a documented decision
([architecture.md § Composition](./architecture.md#composition-guidance)). The
limiter stays a limiter.

### D-005 A failing task is isolated to itself

**Status:** Accepted · **Source:** `CLAUDE.md` § RateController

**Decision.** A task that throws is isolated to that single task: the failure is
surfaced via the error event and to its own caller, and the queue and workers
continue unaffected. One task failing never disrupts the rest.

## Retries

### D-010 The retry budget is named Attempts and includes the initial execution

**Status:** Accepted, with open items · **Source:** Q&A Q8 and its addendum

**Context.** "3 retries" is ambiguous: three executions, or four?

**Decision.** The public configuration field is **`Attempts`** — or equivalent
total-attempts wording — and it **includes the initial execution**. `Attempts = 3`
means at most three executions overall. It is never named `Retries` and never
described as a retry count.

**Consequences.** `Attempts = 1` means retrying is off. Supersedes
[S-001](#s-001-retry-count-semantics).

**Open.** The default value.

### D-011 RetryDecorator retries every ordinary failure by default

**Status:** Accepted, with open items · **Source:** Q&A Q7

**Decision.** With no retry predicate supplied, retry every ordinary failure
automatically. A simple fixed delay must be configurable **without defining any
predicate at all**. Advanced users opt into complex, explicit retry conditions.

**Consequences.** The friendly path requires no predicate, which is the whole
point ([D-102](#d-102-progressive-disclosure-sensible-defaults-advanced-opt-in)).

**Open.** The cross-language definition of an "ordinary failure".

### D-012 Cancellation is terminal during retry

**Status:** Accepted · **Source:** Q&A Q6

**Decision.** Cancellation immediately stops retry and backoff, is never retried,
and **can never be overridden by the user's retry predicate**. The predicate is
not consulted for cancellation at all.

**Consequences.** A retry-everything predicate still cannot resurrect a cancelled
operation. This is a rule, not a default.

### D-013 A retrying job releases its concurrency slot during backoff

**Status:** Accepted · **Source:** Q&A Q4; `CLAUDE.md` § Retry Decorator

**Context.** If one logical job kept its in-flight slot across every attempt and
delay, a retry storm would park every slot in a sleep.

**Decision.** A failed attempt releases its in-flight slot **before** waiting.

**Consequences.** Backoff is free of concurrency cost, and retry-outside-limiter
becomes the recommended composition.

### D-014 Two retry API styles: awaited and deferred

**Status:** Accepted, with open items · **Source:** Q&A Q4

**Decision.** Support both an **awaited retry path**, and a **deferred
fire-and-forget retry path** that places failed work into a delayed /
dead-letter-style queue and reports ultimate success or failure through an event.

**Open.** The exact API shape and naming, and the boundary between a delayed retry
queue and terminal dead-letter storage.

### D-015 Awaited retries re-enter normal admission

**Status:** Accepted, with open items · **Source:** Q&A Q5

**Decision.** Awaited retries re-enter normal admission rather than bypassing it,
acquiring a new in-flight slot for each attempt.

**Open.** What happens when a retry re-enters a **full** bounded queue.

### D-016 Retry scheduling priority is configurable

**Status:** Accepted, with open items · **Source:** Q&A Q5

**Decision.** Three modes: **full retry prioritization** (the retry jumps ahead),
**no prioritization** (normal queued work goes first), and **probabilistic
prioritization** (a configurable probability `X` decides). The goal is timely
retries that never starve normal queued jobs.

**Open.** The default mode, and exact arbitration and starvation guarantees for
all three. Probabilistic mode requires an injectable random source for
deterministic tests.

### D-017 Exhausted retries surface an aggregated error

**Status:** Accepted · **Source:** `CLAUDE.md` § Retry Decorator

**Decision.** Wherever possible, return an aggregated exception — the combination
of **all** errors encountered during the retry attempts, not only the last.
Per-attempt hooks and callbacks give full visibility; backoff is computed from a
context of the item, the received error, and current metrics.

**Open.** Whether the aggregate includes errors from attempts the predicate
declined to retry.

## ParallelWorkers

### D-020 Worker count comes from a user sampling function

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Parallel Workers

**Decision.** The number of active workers is determined by a user-supplied
sampling function plus a sample interval. The function receives a context of
metrics and data and returns the desired number of active workers at that
evaluation.

**Consequences.** Scaling policy is injected, not configured by enum
([design-principles.md](./design-principles.md#policy-versus-mechanism)).

**Open.** Default min/max counts, the default interval, whether the sampler runs
at startup, and its behavior while a resize is settling.

### D-021 Worker count changes by one per sample by default

**Status:** Accepted · **Source:** `CLAUDE.md` § Parallel Workers

**Decision.** By default the worker count changes by one at a time per sample —
analogous to Kubernetes scaling pods one at a time. The user may optionally define
a **max delta**: the maximum number of worker changes, adding or killing, allowed
per sampling interval.

### D-022 Workers drain gracefully and are never revived

**Status:** Accepted · **Source:** `CLAUDE.md` § Parallel Workers

**Decision.** Dying workers are treated with patience: they stop reading more
items from the queue, finish their current task, and only then disappear — never
cancelled mid-work. A worker marked dead is **never revived**; if capacity is
needed again, a fresh worker is spun up. Kill and recreate, never resurrect.

**Consequences.** The worker state machine has no transition out of `Dead`, which
is what keeps it simple ([INV-8](./architecture.md#invariants)).

## Queue and admission

### D-030 A full queue rejects immediately by default

**Status:** Accepted, with open items · **Source:** Q&A Q20; `CLAUDE.md` § Queues and Data Reliability

**Decision.** When a bounded queue is full, insertion **fails immediately**. The
queue never waits for space; waiting is available only through the explicit
await-insertion mode.

**Consequences.** The default is the only option with bounded memory. A friendlier
default would hide unbounded waiter growth.

**Open.** The default capacity ([D-003](#d-003-queues-are-always-bounded)).

### D-031 Await insertion is the only waiting mode, and it is advanced

**Status:** Accepted, with open items · **Source:** Q&A Q20, Q21

**Decision.** In await-insertion mode new tasks wait on **admission itself**;
callers can hold a number of tasks pending their own insertion, and as the queue
drains those tasks are admitted and processed in turn. It is an advanced,
explicitly chosen mode.

**Open.** Exactly which utilities inherit this and the other queue policies.

### D-032 Admission waiters are uncapped and the caller's responsibility

**Status:** Accepted · **Source:** Q&A Q21

**Decision.** Limitee does **not** cap the number of callers waiting outside a
full queue. That memory and backpressure responsibility — including any unbounded
set of admission waiters — belongs to the caller, who composes their own upstream
controls, such as web-controller or middleware rate limiting. The default API
stays dead simple: full queues fail immediately.

### D-033 No FIFO guarantee for admission waiters

**Status:** Accepted · **Source:** Q&A Q22

**Decision.** Admission order among callers awaiting insertion is
implementation-dependent. Strict FIFO adds unnecessary complexity and is not
required.

**Consequences.** No test may assert FIFO among waiters
([QA-006](./testing.md#queue-and-admission-qa)).

### D-034 Cancellation while awaiting insertion is immediate and final

**Status:** Accepted, with open items · **Source:** Q&A Q23

**Decision.** Cancellation while awaiting insertion immediately removes the
pending request and guarantees it never enters the queue later.

**Open.** The exact atomic rule when admission and cancellation become ready
concurrently.

### D-035 Timeout scopes are distinct per lifecycle stage

**Status:** Accepted, with open items · **Source:** Q&A Q15, Q16

**Decision.** Four distinct scopes: **pre-admission** (optional, before the item
gains entry), **queue-wait** (while waiting under backlog), **execution** (once
work is running — it **signals cancellation to the running function** rather than
only timing out the callers), and a **possible separate whole-batch-function
timeout**. Once an item is dequeued into a batch and execution begins, its
queue-wait timeout no longer applies; the execution policy takes over. The
accumulation interval is batching behavior, not a failure timeout.

**Open.** Whether the whole-batch timeout exists, whether execution deadlines are
batch-wide or per item, and behavior when user code ignores a cancellation signal.

### D-036 A queue-wait timeout removes the item permanently

**Status:** Accepted, with open items · **Source:** Q&A Q14

**Decision.** On queue-wait timeout the item is **removed and guaranteed never to
execute later**. The caller does not merely stop waiting while the item lingers.

**Open.** The atomic race rule when timeout and the execution claim become ready
concurrently. Minimum guarantee until then: the item resolves exactly once.

### D-037 A cancelled item never runs

**Status:** Accepted · **Source:** Q&A Q14 clarification; `CLAUDE.md` § AsyncAccumulator

**Decision.** If a queued item's main task has been cancelled, that item must not
run at all, even if it still physically resides in the queue.

## Accumulators

### D-040 AsyncAccumulator invokes one true batch function per batch

**Status:** Accepted · **Source:** Q&A Q9

**Context.** "Batching" could mean one call with many inputs, or many calls
started together.

**Decision.** `AsyncAccumulator` accumulates inputs into batches and invokes **one
batch operation per batch**, returning per-input outcomes. It does not invoke each
item's own function while merely starting them together.

### D-041 AsyncAccumulator does not integrate with RateController

**Status:** Accepted · **Source:** Q&A Q9

**Decision.** `AsyncAccumulator` does **not** integrate with or submit work to
`RateController`. A caller who wants both wraps the function with `RateController`
themselves, in whichever composition order they choose. That is user composition,
not the accumulator's responsibility.

### D-042 Outcome correlation is positional by default, keyed is advanced

**Status:** Accepted, with open items · **Source:** Q&A Q10

**Decision.** Default to positional input/output correlation — a same-length
sequence in input order — with an advanced keyed/ID-based correlation option for
callers who need reordered or partial-result handling.

**Open.** Keyed-correlation edge cases (missing, duplicate, unknown keys) and the
exact C# surface.

### D-043 Fewer outcomes than inputs fails only the unmatched inputs

**Status:** Accepted · **Source:** Q&A Q11

**Decision.** In positional mode, deliver every matching positional outcome
normally and fail only the unmatched inputs. **Never fail the entire batch.**

### D-044 Surplus positional outcomes are a contract error

**Status:** Accepted, with open items · **Source:** Q&A Q12

**Decision.** If positional mode returns more outcomes than inputs, surface a
contract error; never silently ignore the surplus.

**Open.** Where the error is surfaced, and whether it changes already-matched
callers' outcomes.

### D-045 A throwing batch function fails every input in that batch

**Status:** Accepted · **Source:** Q&A Q13

**Decision.** If the batch function throws before returning results, every input
in that batch completes with the same batch-level failure.

### D-046 Batching runs on ParallelWorkers with no fixed cadence

**Status:** Accepted · **Source:** Q&A Q9, Q17, Q18

**Decision.** Batching concurrency is implemented through `ParallelWorkers`, whose
long-lived looping batching workers accumulate queued items and invoke the batch
function repeatedly. While queued work remains, a worker invokes consecutive
batches **immediately** — there is no fixed cadence, and the next interval does not
wait on the previous batch function's duration.

**Consequences.** Supersedes a standalone parallel-groupers knob
([S-003](#s-003-a-standalone-parallel-groupers-knob)).

### D-047 The accumulation window starts when the first item arrives after idle

**Status:** Accepted, with open items · **Source:** Q&A Q17, Q19

**Decision.** Once the queue is empty no countdown runs. The **first new item to
arrive starts the full configured accumulation interval**, so it gets the whole
window to collect peers. Within that window, if the batch still has room, keep
waiting for more items; when the window elapses, **flush the partial batch
immediately** rather than waiting to fill it — with tens of thousands of incoming
jobs, waiting would add unacceptable latency.

**Open.** Ownership of the first-item window when several batching workers are
idle.

### D-048 Prefer event-driven waiting; poll at the batching interval

**Status:** Accepted, with open items · **Source:** Q&A Q19 implementation guidance

**Decision.** Prefer event-driven waiting wherever the language supports it — for
example awaiting the next item from a C# `Channel`. Where polling is necessary,
poll at the same configured batching interval. The exact low-level implementation
may be language-dependent; the observable behavior may not be.

**Open.** The latency semantics of polling implementations.

## Weighted batching

### D-050 A batch never overshoots max weight

**Status:** Accepted · **Source:** `CLAUDE.md` § WeightedAsyncAccumulator

**Decision.** When reading an item from the queue, if adding it would push the
batch over max weight, it is **not** added to the current batch — it starts the
next batch instead, carried over and run separately. Batches flush just under max
weight, never above it.

### D-051 A single over-max item runs alone in flexible mode, is blocked in strict mode

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § WeightedAsyncAccumulator

**Decision.** If one item's own weight exceeds the group's max weight and the user
has opted to allow it onto the queue, it runs as a **single-item batch** (flexible
mode). Otherwise it is **blocked** (strict mode).

**Consequences.** This is the only case where a batch may exceed max weight, and
it does so with exactly one item ([INV-9](./architecture.md#invariants)).

**Open.** Which mode is the default.

### D-052 Item weight is computed once at insertion

**Status:** Accepted · **Source:** `CLAUDE.md` § WeightedAsyncAccumulator

**Context.** The user's weight function may be heavy.

**Decision.** Compute each item's weight at insertion time and store it alongside
the item — a context or wrapper holding the item plus its precomputed weight, or a
dictionary. The batching hot path only **reads** the stored weight to decide
admission, never recomputing.

**Consequences.** The admission lock stays tight and an expensive weight function
is tolerated.

### D-053 The weighted admission sequence must be atomic

**Status:** Accepted · **Source:** `CLAUDE.md` § WeightedAsyncAccumulator

**Decision.** The peek → check weight → commit to batch → remove from channel
sequence is a genuine concurrency hazard and must be properly synchronized — for
example semaphores guarding the channel read, so the weight check and the
admission are atomic. **Thread safety here is critical, especially in C#.** This
is subtle and requires careful design in every language.

## Grouping

### D-060 Groups are static

**Status:** Accepted · **Source:** `CLAUDE.md` § GrouppedRateController

**Decision.** Groups are defined upfront, never created or changed at runtime.
Dynamic grouping is deliberately out of scope: too complex, and it introduces
idle-group cleanup and memory-leak concerns not worth taking on.

### D-061 Unmatched items route to a default group or throw

**Status:** Accepted · **Source:** `CLAUDE.md` § GrouppedRateController

**Decision.** Matching is by per-group predicate. When an item matches no group,
behavior is configurable: route it to a **default group**, or **throw** if no
default group is enabled. Whether a default group exists is itself a
configuration choice.

### D-062 Per-group limits plus a shared global ceiling

**Status:** Accepted, with open items · **Source:** Q&A Q24

**Decision.** Enforce both numeric per-group concurrency limits **and** a numeric
shared global concurrency ceiling. Groups are not fully independent, so total
concurrency never reaches the sum of their limits. Allocation of the shared global
capacity must be normalized relative to both the number of active/contending
groups and the global worker/slot count.

**Consequences.** Rejects [S-005](#s-005-fully-independent-groups-summing-to-total-concurrency).

**Open.** The normalization algorithm, integer-remainder handling, the definition
of an active/contending group, unused-capacity redistribution, and the public API
shape.

### D-063 Fair rotation by default, caller priorities advanced

**Status:** Accepted, with open items · **Source:** Q&A Q25

**Decision.** When a shared global slot opens and several groups have queued work,
the next group is chosen by **fair rotation** among competing groups by default.
Caller-assigned group priorities are an advanced API option.

**Open.** The exact fair-rotation algorithm, and how advanced priorities interact
with fairness and starvation.

## Lifecycle

### D-070 Shutdown is either drain or cancel pending

**Status:** Accepted, with open items · **Source:** Q&A Q3; `CLAUDE.md` § Lifecycle and Disposal

**Decision.** On dispose, shut down with one of two user-chosen behaviors and only
then tear everything down: **drain** — let jobs already in the queue finish
processing; or **cancel pending** — cancel every queued-but-not-started job. Jobs
already executing are **not** included in that cancellation instruction and may
finish under their normal behavior.

**Consequences.** Cancel-pending is the explicit, announced exception to the
"every queued job is processed" invariant
([INV-1](./architecture.md#invariants), [INV-2](./architecture.md#invariants)).

**Open.** The disposition of callers already awaiting insertion when shutdown
begins; whether disposal is idempotent.

### D-071 Enqueues stop immediately once shutdown begins

**Status:** Accepted · **Source:** Q&A Q3

**Decision.** In both shutdown modes, stop accepting new enqueues immediately; any
enqueue attempted after shutdown begins fails with cancellation.

### D-072 Job persistence across restarts is out of scope

**Status:** Accepted · **Source:** `CLAUDE.md` § Lifecycle and Disposal

**Decision.** Job persistence across crashes and restarts is explicitly out of
scope. The reliability guarantee holds only within the running process lifetime,
with no durable-queue headache. Users who need a persistent queue add that layer
themselves; the library does not take on that dependency. Within the process
lifetime, reliability must be complete and precise.

## Distributed coordination

### D-080 In-memory by default; Redis is opt-in

**Status:** Accepted · **Source:** `CLAUDE.md` § Deployment Model

**Decision.** In-memory / in-process by default, with an optional ability to scale
out to a Redis cluster acting as a shared tracker, to synchronize rate control
across multiple processes in different services.

### D-081 Enabling Redis coordinates every utility

**Status:** Accepted · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** When Redis is enabled, **everything is coordinated** across
instances: `RateController` concurrency, `ParallelWorkers`, and the accumulators.

**Open.** Whether coordination can be enabled per utility or only process-wide.

### D-082 Distributed counting is set-based, never increment or decrement

**Status:** Accepted · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Context.** A dropped acknowledgement on an increment leaves a counter
permanently wrong, and a retried decrement double-counts.

**Decision.** Never use increment/decrement — that loses idempotency on retry.
Each counted entity has a specific ID and joins a Redis **set**; to release, it
removes **its own ID** from the set. The effective count is the **cardinality of
the set**, which is far more accurate and retry-safe than a mutated number.

### D-083 A Redis outage fails open to local continuation

**Status:** Accepted · **Source:** Q&A Q1

**Decision.** Redis must never become a dependency whose outage disables the
application. Each process periodically samples the active worker/process count,
roughly once per minute. If Redis becomes unavailable, the process keeps running
and uses the **last sampled count** to divide the global allowance locally until
Redis recovers.

**Consequences.** Slow membership changes may cause a gradual, **bounded
overshoot** of the global ceiling. That tradeoff is accepted deliberately, and it
is the one documented exception to the hard coordinated ceiling
([D-002](#d-002-n-is-the-hard-global-in-flight-ceiling)). Rejects
[S-008](#s-008-failing-closed-during-a-redis-outage).

### D-084 Membership during an outage is configurable; frozen is defined

**Status:** Accepted, with open items · **Source:** Q&A Q1

**Decision.** Two policies. **Frozen membership:** treat the last sampled count as
the baseline — do not add capacity or account for newly appearing workers;
removals may only reduce the effective capacity/allocation, never increase it.
**Non-frozen membership:** supported as a configuration choice, but its exact
behavior is deferred.

**Open.** The non-frozen policy, and which policy is the default.

### D-085 Redis access goes through a user-supplied adapter

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** The library does not bundle or control a specific Redis library.
Users inject their own adapter — how to connect, how to read values, how to
execute commands — so any Redis client works. Design goal: adaptive, comfortable,
and highly customizable.

**Consequences.** The adapter is also the test seam: a fake in-memory adapter plus
an injected clock makes outage and recovery deterministic.

**Open.** The exact adapter interface, especially for multi-key and scripted
operations.

### D-086 Liveness is a distributed self-cleaning protocol

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** Three mechanisms keep stale IDs from crashed instances from
inflating the set forever: **graceful removal on clean death**; a **heartbeat /
keep-alive service** started whenever Redis is enabled for any utility, on a
user-configurable interval; and a **last-seen timestamp plus peer
disqualification**, where workers periodically scan the sets and evict any member
whose keep-alive has gone stale. This is fully distributed — any worker can prune
dead peers, so there is no single reaper.

**Open.** Default heartbeat interval and staleness threshold.

### D-087 Cluster compliance requires deliberate selective slotting and a user prefix

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** Cluster compliance is a hard requirement. (1) Any operation touching
multiple keys together must ensure those keys land in the same hash slot, using
hash tags; **every multi-key operation is an explicit slotting design point and
must be called out, not assumed.** (2) The user can define a **prefix** for all
Limitee keys, so the library coexists with a Redis instance used for other
purposes, and so multiple controllers across services can intentionally share or
isolate coordination. (3) **Slot selectively, not globally**: keys only ever
touched on their own slot naturally; impose hash tags only where an operation
genuinely reads multiple keys together, such as the liveness scan.

**Open.** Whether the membership set and the last-seen timestamp key share a hash
tag — undecided, pending the final counting mechanism.

## Observability

### D-090 Observability is event-driven and exposes raw data

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Observability, § Notes

**Decision.** Build around an event-driven architecture with a rich set of niche
events, exposing data **raw** so each developer wires it into their own
observability as they see fit. Every utility also lets users read current state
and statistics — queue depth, in-flight counts, rate and batch metrics — which is
important for metrics and is public API.

**Open.** Exact payload shapes, delivery synchronicity, and ordering guarantees.

### D-091 OTel is a separate opt-in package per language

**Status:** Accepted · **Source:** `CLAUDE.md` § Observability

**Decision.** On top of the raw data there is an optional OpenTelemetry wrapper: a
**separate opt-in package per language**, living in the same monorepo, so the core
carries **zero OTel dependency**. The user brings and configures their own OTel
setup; overriding directive — always give the user a way to customize it.

### D-092 User traces pass through cleanly; library spans are targeted

**Status:** Accepted · **Source:** `CLAUDE.md` § Observability

**Decision.** The user's own function traces pass through cleanly, without the
library's boundaries or overhead polluting them — the user's code dominates the
span tree. On top of that, a few targeted spans are injected around the library's
own stages (wait time, batch size, which batch), so the user can diagnose when
slowness comes from the library rather than from their own code.

## Project-wide

### D-100 Native reimplementation per language, no shared core

**Status:** Accepted · **Source:** `CLAUDE.md` § Implementation Strategy

**Decision.** Full native reimplementation per language. Targets share only the
design and behavior spec, not code — no shared Rust core with thin bindings.

**Rationale.** (1) **No FFI marshalling/overhead** — a shared core forces a
boundary crossing per operation, and for cheap rate-limiter operations the
crossing can cost more than it saves. (2) **Passing functions must be
first-class** — the API accepts user functions directly, and passing functions
across FFI is painful. (3) A shared core's real benefit would be
correctness/maintainability, not speed, and that is outweighed here by flexibility
and nativeness — and recovered through the shared test spec.

**Consequences.** Rejects [S-006](#s-006-a-shared-rust-core-with-thin-bindings).
Parity rests entirely on [D-105](#d-105-business-tests-come-from-one-shared-markdown-spec).

### D-101 API surfaces are idiomatic per language

**Status:** Accepted · **Source:** `CLAUDE.md` § API Shape

**Decision.** Surfaces are hand-picked and custom to each language's conventions:
`async`/`await` in C# and TypeScript, idiomatic futures in Rust, channels and
contexts in Go, idiomatic Python. **Behavior is identical across all targets; only
the surface differs.** A unified API that doesn't match a language's conventions
would damage the codebase of the people adopting the library.

**Consequences.** Planned targets are C#, TypeScript, Rust, Go, and Python. A
target is not real until its binding exists
([testing.md](./testing.md#implementation-status)).

### D-102 Progressive disclosure: sensible defaults, advanced opt-in

**Status:** Accepted · **Source:** `CLAUDE.md` § Configuration Philosophy; Q&A closing notes

**Decision.** Simple by default for casual users; deeply customizable for advanced
users. APIs must be dead simple for beginners, which means defaulting every
behavior and value sensibly. Nuanced behavior is opt-in through properties or
function injection — never required up front. Guiding principle: simple for simple
users, fully customizable for advanced ones, without the maintainer losing their
sanity over the codebase.

### D-103 The clock is public API

**Status:** Accepted · **Source:** `CLAUDE.md` § Configuration Philosophy, § Testing Strategy

**Decision.** Timing-dependent behavior is tested against an injectable clock,
required to keep timing tests fast and deterministic, and every language's API
must support it. It is part of the **public API**: it exists primarily so tests can
control time, but advanced users can swap it in if they want.

### D-104 Prefer functions and events over object orientation

**Status:** Accepted · **Source:** `CLAUDE.md` § Notes

**Decision.** Maximize passing functions and events rather than relying on OOP.
OOP is still used where a lifetime must be owned and disposed, but not as the
primary structure. In C# and Rust, use functional programming paradigms and
features, plus the newest language features and best practices available.

### D-105 Business tests come from one shared Markdown spec

**Status:** Accepted · **Source:** `CLAUDE.md` § Testing Strategy

**Decision.** Tests split into **business tests** — core logic and API behavior
that must be identical across languages, driven from one shared spec — and
**technical tests** — language-specific behavior that doesn't generalize, tested
per language with variation. The shared business spec is written in Markdown and
is the **single source of truth**
([testing.md](./testing.md)). An LLM generates the appropriate native tests per
language from it; generated tests are then committed and maintained as normal code
going forward, not regenerated blindly.

### D-106 Stable case IDs trace every binding's tests

**Status:** Accepted · **Source:** `CLAUDE.md` § Testing Strategy

**Decision.** Every business test case gets a stable ID — a component prefix plus a
number, such as `RC-001` or `AA-001`. Each language's test carries its case ID in
a comment above the test, so when a spec case changes the ID locates every
language's implementation of that case and keeps all languages compliant with the
Markdown.

### D-107 Working name is Limitee

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Name

**Decision.** The working name is **Limitee**. Not a favorite aesthetically, but it
was verified available across all five target ecosystems — a hard constraint, since
npm and PyPI are among the largest registries in the world and a name free across
all five is rare. Availability wins.

**Open.** This repository's directory is named `Limitful`, and the README header
says `Limitee`. The mismatch is unexplained and should be reconciled — see
[Unresolved items](#unresolved-items).

### D-108 High-concurrency efficiency and impeccable DX are explicit goals

**Status:** Accepted · **Source:** `CLAUDE.md` § Notes

**Decision.** Everything is designed to handle high-concurrency environments
efficiently, and every implementation must be as efficient, robust, and
maintainable as possible. The developer experience of this functionality must be
impeccable — functionally inclined (including in C#), friendly, and easy to use
across all supported languages. Every utility lets users access current state and
statistics, which is important for metrics
([D-090](#d-090-observability-is-event-driven-and-exposes-raw-data)).

**Consequences.** Performance and ergonomics are review criteria, not
afterthoughts. A correct implementation that allocates on the admission hot path,
or that forces ceremony on a simple caller, is not finished.

### D-109 A docs site with per-utility examples and a playground is a deliverable

**Status:** Accepted, with open items · **Source:** `CLAUDE.md` § Notes

**Decision.** Beyond comprehensive documentation and examples for all utilities in
every supported language, the project ships a **docs site** that looks good and is
easy to navigate, with clear examples and explanations for each utility, including
a link to a **Replit playground** where users can experiment with the classes.

**Open.** The site's tooling, hosting, structure, and the playground's contents.
The design documents in `docs/` are the content source, not the site itself.

## Superseded and rejected

Preserved deliberately. These are the readings and alternatives that were
considered and closed; the reasoning is what prevents them being re-proposed.

### S-001 Retry-count semantics

**Status:** Superseded by [D-010](#d-010-the-retry-budget-is-named-attempts-and-includes-the-initial-execution)

Naming the budget `Retries`, or describing it as a count of retries *after* the
initial call, so that `3` would mean four executions. Rejected as ambiguous. The
public field is `Attempts` and includes the initial execution.

### S-002 100 ms as the default retry delay

**Status:** Superseded by [D-011](#d-011-retrydecorator-retries-every-ordinary-failure-by-default)

The 100 ms figure in the round-3 Q&A reads like a chosen default. It is explicitly
**an ease-of-configuration example, not a default**: the requirement is that a
simple fixed delay be settable without defining a predicate. The actual default
delay, backoff curve, and jitter remain undecided.

### S-003 A standalone parallel-groupers knob

**Status:** Superseded by [D-046](#d-046-batching-runs-on-parallelworkers-with-no-fixed-cadence)

`CLAUDE.md` originally listed "the amount of parallel groupers (maybe not for all
programming languages)" as its own AsyncAccumulator option. It is now expressed as
the `ParallelWorkers` batching-worker count, so scaling, drain, and events are
inherited rather than duplicated. The per-language caveat survives as a
[technical-test](./testing.md#technical-tests) concern: achievable parallelism
differs, semantics do not.

### S-004 RateController as a time-window rate limiter

**Status:** Rejected by [D-001](#d-001-ratecontroller-limits-by-concurrency-not-by-time-window)

The name invites a fixed window, sliding window, token bucket, or per-second cap.
None of those is what `RateController` does. A separate per-second limiter is
under consideration as a *different* utility and remains
[unresolved](#unresolved-items).

### S-005 Fully independent groups summing to total concurrency

**Status:** Rejected by [D-062](#d-062-per-group-limits-plus-a-shared-global-ceiling)

Letting each group have its own limit with no shared ceiling, so total concurrency
could reach the sum of group limits. Rejected: the shared global ceiling is the
reason the utility exists. Composing several independent `RateController`s has
exactly this flaw.

### S-006 A shared Rust core with thin bindings

**Status:** Rejected by [D-100](#d-100-native-reimplementation-per-language-no-shared-core)

Write the tricky logic once in Rust and bind it everywhere. Rejected on FFI
marshalling cost per operation, the pain of passing user functions across the
boundary, and the loss of nativeness. The correctness benefit is recovered through
the shared business test spec instead.

### S-007 Unbounded queues and drop-oldest overflow

**Status:** Rejected by [D-003](#d-003-queues-are-always-bounded) and [INV-1](./architecture.md#invariants)

Unbounded growth is a memory failure at scale. Dropping the oldest item is silent
data loss. Neither is available in any utility, in any configuration.

### S-008 Failing closed during a Redis outage

**Status:** Rejected by [D-083](#d-083-a-redis-outage-fails-open-to-local-continuation)

Stop admitting work during a Redis outage to preserve the global ceiling exactly.
Rejected: Redis must never be a dependency whose outage disables the application.
Bounded overshoot is the accepted price.

## Unresolved items

Every open question in one place. Each is owned by a document that will record the
answer. **A blocked test case must never be implemented by guessing**
([testing.md § Cross-language parity](./testing.md#cross-language-parity-process)).

| Area | Question | Owner | Origin |
| --- | --- | --- | --- |
| Rate limiting | Whether a separate per-second rate limiter utility is built at all | [rate-controller.md](./utilities/rate-controller.md#open-items) | `CLAUDE.md` |
| Rate limiting | Default `maxQueued`, and default execution timeout | [queue-and-admission.md](./subsystems/queue-and-admission.md#open-items) | Consolidation |
| Retries | API shape and naming of the awaited and deferred paths | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q4 |
| Retries | Delayed-retry versus terminal dead-letter semantics | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q4 |
| Retries | Re-admission behavior when a retry hits a full bounded queue | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q5 |
| Retries | Default `Attempts`, default delay, backoff curve, and jitter | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q7 |
| Retries | The cross-language definition of an "ordinary failure" | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q7 |
| Retries | Default priority mode, and arbitration and starvation guarantees for all three | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Q&A Q5 |
| Retries | Whether the deferred path's delayed queue is bounded, and its overflow policy | [retry-decorator.md](./utilities/retry-decorator.md#open-items) | Consolidation |
| Batch outcomes | Keyed-correlation edge cases: missing, duplicate, unknown keys | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q10 |
| Batch outcomes | The exact C# surface | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q10 |
| Batch outcomes | Where a surplus-outcome contract error surfaces, and its effect on matched callers | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q12 |
| Timeouts | Atomic race rules when timeout or cancellation and the execution claim or admission become ready together | [queue-and-admission.md](./subsystems/queue-and-admission.md#open-items) | Q&A Q14, Q23 |
| Timeouts | Whether a separate whole-batch-function timeout exists | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q16 |
| Timeouts | Whether execution deadlines are batch-wide or per item | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q16 |
| Timeouts | Behavior when user code ignores a cancellation signal | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q16 |
| Batching workers | Ownership of the first-item accumulation window when several workers are idle | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q19 |
| Batching workers | Latency semantics of polling implementations | [async-accumulator.md](./utilities/async-accumulator.md#open-items) | Q&A Q19 |
| Queue policy | Exactly which utilities inherit reject-by-default, uncapped waiters, waiter ordering, and cancellation behavior | [queue-and-admission.md](./subsystems/queue-and-admission.md#open-items) | Q&A Q20–Q23 |
| Weighted batching | Whether strict or flexible is the default over-max policy | [weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md#open-items) | Consolidation |
| Weighted batching | Whether size and weight bounds may be combined, and precedence | [weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md#open-items) | Consolidation |
| Weighted batching | Zero, negative, and throwing weight results | [weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md#open-items) | Consolidation |
| Grouping | Public API shape | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Q&A Q24 |
| Grouping | Normalization and integer-remainder algorithm | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Q&A Q24 |
| Grouping | Definition of an active/contending group | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Q&A Q24 |
| Grouping | Unused-capacity redistribution | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Q&A Q24 |
| Grouping | Fair-rotation algorithm and advanced-priority interaction | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Q&A Q25 |
| Grouping | Predicate evaluation order and multi-match behavior | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Consolidation |
| Grouping | Whether `GroupedRateController` is one shared admission layer or per-group controllers plus an arbitrator | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Consolidation |
| Naming | `GroupedRateController` versus the earlier `GrouppedRateController` spelling | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Consolidation |
| Shutdown | Disposition of callers already awaiting insertion when shutdown begins | [queue-and-admission.md](./subsystems/queue-and-admission.md#open-items) | Q&A Q3 |
| Shutdown | Whether disposal is idempotent | [architecture.md](./architecture.md#open-items) | Consolidation |
| Workers | Default min/max worker counts and default sampling interval | [parallel-workers.md](./utilities/parallel-workers.md#open-items) | Consolidation |
| Workers | Whether the sampler runs at startup, and its behavior during a settling resize | [parallel-workers.md](./utilities/parallel-workers.md#open-items) | Consolidation |
| Redis | The non-frozen membership policy and which policy is the default | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Q&A Q1 |
| Redis | Whether the membership set and last-seen key co-locate under one hash tag | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | `CLAUDE.md` |
| Redis | Division of `N` across processes, including integer remainders | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Consolidation |
| Redis | The exact adapter interface for multi-key and scripted operations | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Consolidation |
| Redis | Default key prefix, heartbeat interval, and staleness threshold | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Consolidation |
| Redis | Whether coordination is per-utility or process-wide | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Consolidation |
| Observability | Event payload shapes, delivery synchronicity, ordering guarantees | [observability.md](./subsystems/observability.md#open-items) | Consolidation |
| Observability | OTel metric and span naming conventions | [observability.md](./subsystems/observability.md#open-items) | Consolidation |
| Project | Library name: `Limitee` is recorded, but this repository is `Limitful` | [D-107](#d-107-working-name-is-limitee) | Consolidation |
| Project | Which binding lands first, and per-language test tooling | [testing.md](./testing.md#open-items) | Consolidation |
| Docs | The docs site's tooling, hosting, structure, and Replit playground contents | [D-109](#d-109-a-docs-site-with-per-utility-examples-and-a-playground-is-a-deliverable) | `CLAUDE.md` § Notes |
