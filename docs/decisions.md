# Decision Log

Durable design decisions for Limitful, consolidated from `CLAUDE.md` and the
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
- [Shared controller contract](#shared-controller-contract)
- [KeyedControllerRegistry](#keyedcontrollerregistry)
- [Supervision, flushing, and shares](#supervision-flushing-and-shares)
- [Outcome classification and adaptive presets](#outcome-classification-and-adaptive-presets)
- [Provider capabilities](#provider-capabilities)
- [Roadmap and scope](#roadmap-and-scope)
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
whatever speed the concurrency configuration allows. Limitful implements a
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
worker count. A provider-specific degraded mode may weaken the coordinated
guarantee only within a documented bound and must report the degradation
([D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)).

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

**Decision.** Limitful does **not** cap the number of callers waiting outside a
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

**Status:** Superseded by [D-163](#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) · **Source:** `CLAUDE.md` § Deployment Model

**Decision.** In-memory / in-process by default, with an optional ability to scale
out to a Redis cluster acting as a shared tracker, to synchronize rate control
across multiple processes in different services.

### D-081 Enabling Redis coordinates every utility

**Status:** Superseded by [D-163](#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** When Redis is enabled, **everything is coordinated** across
instances: `RateController` concurrency, `ParallelWorkers`, and the accumulators.

**Open.** Whether coordination can be enabled per utility or only process-wide.

### D-082 Distributed counting is set-based, never increment or decrement

**Status:** Accepted, clarified by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Context.** A dropped acknowledgement on an increment leaves a counter
permanently wrong, and a retried decrement double-counts.

**Decision.** Never use increment/decrement — that loses idempotency on retry.
Each counted entity has a specific ID and joins a Redis **set**; to release, it
removes **its own ID** from the set. The effective count is the **cardinality of
the set**, which is far more accurate and retry-safe than a mutated number.

### D-083 A Redis outage fails open to local continuation

**Status:** Superseded in generality by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) · **Source:** Q&A Q1

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

**Status:** Accepted for the Redis divided-allocation mode, clarified by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract), with open items · **Source:** Q&A Q1

**Decision.** Two policies. **Frozen membership:** treat the last sampled count as
the baseline — do not add capacity or account for newly appearing workers;
removals may only reduce the effective capacity/allocation, never increase it.
**Non-frozen membership:** supported as a configuration choice, but its exact
behavior is deferred.

**Open.** The non-frozen policy, and which policy is the default.

### D-085 Redis access goes through a user-supplied adapter

**Status:** Superseded as a controller boundary by [D-163](#d-163-synchronizationprovider-is-the-backend-neutral-public-contract); retained inside the Redis provider by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract), with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** The library does not bundle or control a specific Redis library.
Users inject their own adapter — how to connect, how to read values, how to
execute commands — so any Redis client works. Design goal: adaptive, comfortable,
and highly customizable.

**Consequences.** The adapter is also the test seam: a fake in-memory adapter plus
an injected clock makes outage and recovery deterministic.

**Open.** The exact adapter interface, especially for multi-key and scripted
operations.

### D-086 Liveness is a distributed self-cleaning protocol

**Status:** Accepted as Redis-provider mechanics, clarified by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract), with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

**Decision.** Three mechanisms keep stale IDs from crashed instances from
inflating the set forever: **graceful removal on clean death**; a **heartbeat /
keep-alive service** started whenever Redis is enabled for any utility, on a
user-configurable interval; and a **last-seen timestamp plus peer
disqualification**, where workers periodically scan the sets and evict any member
whose keep-alive has gone stale. This is fully distributed — any worker can prune
dead peers, so there is no single reaper.

**Open.** Default heartbeat interval and staleness threshold.

### D-087 Cluster compliance requires deliberate selective slotting and a user prefix

**Status:** Accepted as Redis-provider mechanics, clarified by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract), with open items · **Source:** `CLAUDE.md` § Redis Distributed Mode

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

**Status:** Superseded by [D-162](#d-162-limitful-is-the-canonical-project-and-library-name) · **Source:** `CLAUDE.md` § Name

**Decision.** The working name is **Limitee**. Not a favorite aesthetically, but it
was verified available across all five target ecosystems — a hard constraint, since
npm and PyPI are among the largest registries in the world and a name free across
all five is rare. Availability wins.

**Open, and now urgent.** The name is **actively split in the documentation**:
`Limitee` in this file, `README.md`, `CLAUDE.md`, `architecture.md`, and the
original utility documents; `Limitful` in `throughput-controller.md`,
`synchronization-provider.md`, and the round-4 additions. The repository directory
is `Limitful`. Newer material consistently uses `Limitful`, which suggests a
rename that was never recorded. **One name must win and the other must be swept**;
until it is recorded here, new documents follow the file-local convention and the
split keeps widening. See [Unresolved items](#unresolved-items).

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

## Shared controller contract

### D-110 A shared controller contract owns submission, job options, and admission queries

**Status:** Accepted, with open items · **Source:** Round-4 grooming; `throughput-controller.md` § Shared controller contract

**Context.** `RateController` and `ThroughputController` had independently
specified submission, job metadata, and admission queries, with the shared surface
documented inside one of the two implementations.

**Decision.** The shared surface is specified once, in
[controller-contract.md](./subsystems/controller-contract.md): submission and the
returned awaitable outcome, `JobOptions`, advisory admission queries, bounded
admission, cancellation, stage deadlines, drain/cancel-pending disposal,
snapshots, and raw events. The two controllers are **peers**; neither is
secondary.

**Consequences.** `KeyedControllerRegistry` can manage any controller without
naming a concrete type ([D-120](#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key)).
A shared interface must never imply that pacing and concurrency have the same
semantics, so the contract document names every divergence explicitly.

### D-111 JobOptions is one shared envelope with per-controller cost semantics

**Status:** Accepted, with open items · **Source:** Round-4 grooming

**Decision.** One immutable submission envelope carries `id`, `priority`, `cost`,
`cancellation`, and `deadline`. **Every field is optional and function-only
submission remains the simple path.** Fields are evaluated once at submission and
stored in the queued envelope, never recomputed inside a scheduling lock.

**Consequences.** `cost` is shared in *name* only: `ThroughputController` spends
credits at launch and never refunds them, while a `RateController` cost would mean
holding several concurrency slots for a job's duration. Collapsing those into one
semantic would be wrong, so each controller documents its own accounting.

### D-112 Priority is optional, banded, and protected by aging

**Status:** Accepted, with open items · **Source:** Round-4 grooming; `throughput-controller.md` § Priority

**Decision.** Priority is an advanced per-job option, neutral and FIFO by default.
It maps to a bounded set of priority bands with stable FIFO order inside each
band — not an arbitrary comparator. When enabled, selection defaults to aging or
weighted-fair service so ordinary work keeps a guaranteed turn; strict priority is
an expert mode that must warn about starvation. Priority changes selection order
only and never bypasses a hard gate.

**Open.** Whether `RetryDecorator`'s three retry-priority modes
([D-016](#d-016-retry-scheduling-priority-is-configurable)) collapse into this
field. Two mechanisms for one concept is a simplification opportunity.

### D-113 Admission estimation is advisory and never reserves capacity

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** `canStartNow` and `estimatedStartAt` report whether and when work
appears admissible. They **never reserve**, never mutate state, and never block. A
result may be stale the moment it returns, and two concurrent callers may both be
told "yes".

**Consequences.** They exist for early load shedding — rejecting an HTTP request
with `Retry-After` when it cannot begin before the client's own timeout — not for
coordinating admission. A caller that treats a query as a reservation has a race,
by design.

### D-114 EstimatedStartAt is best-effort and may be absent

**Status:** Accepted · **Source:** Round-4 grooming, pushback on uniform estimation

**Context.** Estimation is not equally honest on both controllers.
`ThroughputController` derives next eligibility deterministically from its pacing
schedule and quota refill. `RateController` cannot: a slot frees when user code
finishes, and the library has no model of user-code duration. A statistical
estimate from observed completion rates is wrong exactly when it matters most —
during a latency spike, when durations stop resembling their history.

**Decision.** `estimatedStartAt` returns the language's absence type when the
controller cannot compute an estimate, and **never fabricates a number**. Where
the value is statistical rather than computed, that distinction is **explicit in
the return value**, not a documentation footnote. The library ships no implicit
predictor of user-code duration; a caller may supply an estimator.

### D-115 Deadline-aware admission rejects at submission with controller-bounded accuracy

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** A `deadline` in `JobOptions` means "accept only if this can begin
before `X`". It is evaluated at submission — rejecting immediately when the
controller can **prove** the earliest possible start is after the deadline — and
again before launch commit, which is the existing queue-wait guarantee
([D-036](#d-036-a-queue-wait-timeout-removes-the-item-permanently)).

**Consequences.** Submission-time rejection is **sound** for
`ThroughputController`, where eligibility is computable, and **conservative only**
for `RateController`, which may reject only on provable infeasibility such as an
unclearable queue. A concurrency controller must never reject at submission on a
statistical estimate: a false rejection is an availability bug the library
invented, whereas letting the deadline expire in the queue is already announced
behavior ([INV-2](./architecture.md#invariants)).

### D-116 Weighted concurrency cost for RateController is deferred

**Status:** Deferred · **Source:** Round-4 grooming, pushback on a uniform cost field

**Context.** `cost` on a concurrency controller means occupying several of `N`
slots. That creates a head-of-line problem with no decided answer: a cost-10 job
with `N = 10` can start only when the controller is fully idle, so under steady
cost-1 traffic it may never start. Letting cheaper jobs pass starves it; making
them wait blocks the queue head behind a job that cannot run.
`ThroughputController` solved the equivalent problem by preserving order and
waiting for the next window — but a concurrency controller has no window. It waits
on user-code completion, which may never arrive.

**Decision.** Weighted concurrency cost is deferred until a bounded-starvation
rule exists. Until then `cost` on `RateController` is **rejected at submission
with a clear error**, not silently ignored — shipping it as ignored would let
callers build on a limit that is not being enforced.

## KeyedControllerRegistry

### D-120 KeyedControllerRegistry creates one controller per dynamic key

**Status:** Accepted, draft design · **Source:** Round-4 grooming; chosen over framework adapters and a QoS partition utility

**Context.** Groups are static and declared upfront
([D-060](#d-060-groups-are-static)), but tenants, API keys, and IP addresses are
discovered at runtime and unbounded in principle. Per-tenant and per-API-key
limiting is the most common real-world limiter requirement and Limitful could not
express it. Rust's Governor validates the demand with a first-class keyed limiter.

**Decision.** Build `KeyedControllerRegistry` first: a lifecycle manager that
resolves each item to a key through a caller-supplied pure selector and creates one
controller per key on first use. It holds no queue, no slots, and no pacing state
of its own, so every existing admission guarantee is inherited unmodified. See
[keyed-controller-registry-draft.md](./utilities/keyed-controller-registry-draft.md).

**Consequences.** Chosen over HTTP/gRPC adapters — which would couple core code to
framework maintenance — and over a QoS partition utility, which needs a scheduler
redesign. Reversible with effort. Doing nothing would leave Limitful strong for
fixed groups and awkward for tenant, IP, and API-key limits.

### D-121 Idle TTL and maximum active keys are mandatory

**Status:** Accepted · **Source:** Round-4 grooming

**Context.** Keys are frequently attacker-controlled. A client sending a random
API key per request would grow registry memory without bound.

**Decision.** `idleTimeToLive` and a finite `maxActiveKeys` are **required
configuration, not options**. There is no "never expire" value and no unbounded
key count. Eviction counts, refusal counts, active-key count, and high-water mark
are always observable, never debug-only.

**Consequences.** This is the one Limitful utility that requires more than its
limit, and the extra required inputs exist solely to make the memory bound
explicit — a deliberate exception to maximizing defaults
([D-102](#d-102-progressive-disclosure-sensible-defaults-advanced-opt-in)).

### D-122 Eviction never discards live work

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** Only a key whose controller has an **empty queue and nothing in
flight** is idle, and only an idle key is evictable. Idle means *empty*, not merely
quiet. Eviction disposes the controller through its normal disposal path, so there
is nothing to drain by construction.

**Consequences.** Forced by [INV-1](./architecture.md#invariants): evicting a
controller with queued work would drop that work unannounced. Reaching
`maxActiveKeys` therefore rejects the newcomer rather than evicting an incumbent.

### D-123 At-capacity refusal is distinct from queue overflow

**Status:** Accepted, with open items · **Source:** Round-4 grooming

**Decision.** A submission refused because the registry is at `maxActiveKeys`
carries its own reason code, distinct from a full queue, so an operator can tell
"this tenant is overloaded" from "we are tracking too many tenants". Separately,
**worst-case aggregate concurrency is `maxActiveKeys × perKeyLimit`** and must be
reported in the snapshot, with an optional `globalCeiling` across all keys included
in the first version.

**Consequences.** Independent per-key controllers reproduce exactly the
arrangement rejected for groups
([S-005](#s-005-fully-independent-groups-summing-to-total-concurrency)); it is
acceptable only because it is bounded, documented, and capped on request.

**Open.** Whether `globalCeiling` should be mandatory rather than recommended. The
argument for mandatory is safety; the argument against is ergonomic only.

### D-124 Registry disposal propagates and evictions are observable

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** Disposing the registry stops accepting new keys and submissions
immediately ([INV-10](./architecture.md#invariants)), disposes every live
controller under the chosen shutdown mode, and returns only once all of them are
disposed. Every key creation, eviction, and at-capacity refusal is an event.

**Consequences.** Raw keys may appear in events but **must not become unbounded
metric labels** — an attacker-controlled key is the cardinality-explosion hazard
that [observability.md](./subsystems/observability.md) warns about.

## Supervision, flushing, and shares

### D-130 Worker failure behavior is an explicit enumerated supervision policy

**Status:** Accepted, with open items · **Source:** Round-4 grooming; resolves a prior open item

**Context.** A failing *task* is isolated ([INV-12](./architecture.md#invariants)),
but a failing *worker loop* is different: if a worker dies and is not replaced,
throughput silently drops and stays dropped. One poisoned worker function must not
leave a controller permanently at half capacity.

**Decision.** Four enumerated policies, plus an optional per-failure callback that
selects among them: **Isolate** (default — surface and keep looping), **Replace**
(retire and start a fresh worker), **Reduce capacity** (retire without replacement,
down to the minimum), and **Stop controller** (drain everything and shut down).
Every outcome emits a worker-failure event, including under `Isolate`, so silent
capacity loss is impossible. Replacement is creation, never revival
([INV-8](./architecture.md#invariants)); retirement stays graceful; and replacement
is rate-limited so a permanently failing worker cannot become a create/destroy
spin.

**Consequences.** Resolves the earlier open question of whether the failure policy
is an enum or a callback: it is both. Supervision answers "what happens to the
worker"; [D-140](#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures)
answers "what does this failure mean for capacity". They are deliberately separate.
Operational lessons are borrowed from Go worker pools such as `ants`, not their API.

**Open.** Replacement backoff default, and whether repeated replacement failures
escalate to `Stop controller` automatically.

### D-131 Batches flush on size, weight, interval, manual request, or shutdown

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** A batch closes for exactly five reasons: `maxBatchSize` reached,
`maxBatchWeight` would be exceeded, the accumulation window elapsed, an explicit
**manual flush**, or shutdown. Manual flush is the new capability: it closes the
current batch immediately, never exceeds a bound, awaits the batch outcomes so it
can be used as a barrier, is a successful no-op when empty, respects composed
admission rather than bypassing it, and coalesces with a concurrent flush.

**Consequences.** Interval-plus-size cannot express "no more input is coming" — end
of an HTTP request, end of a file, or a test asserting a deterministic batch
boundary. Manual flush fills that gap without changing the window rules
([D-047](#d-047-the-accumulation-window-starts-when-the-first-item-arrives-after-idle)).

### D-132 Reserved group shares are accepted in direction and deferred in scope

**Status:** Deferred · **Source:** Round-4 grooming

**Context.** Per-group limits are maximums; they say how much a group **may** take,
never how much it is **guaranteed**. Under contention a group can be squeezed to
zero by the shared ceiling while still below its own limit, because fair rotation
distributes opportunities rather than capacity.

**Decision.** Optional reserved/minimum shares of the shared ceiling, with unused
reservation reclaimable by other groups, are accepted as a direction and deferred
out of the first version. Reservations are floors and limits are ceilings; both
bind. Reserved shares must sum to at most the shared ceiling, validated at
construction. Reclaimed capacity is surrendered on in-flight completion, never by
preemption.

**Consequences.** Stronger than priority — the difference between "checkout usually
wins" and "checkout always has 20 percent" — but it depends on the shared-capacity
normalization algorithm that is still undecided
([D-062](#d-062-per-group-limits-plus-a-shared-global-ceiling)). Layering guaranteed
floors on an undefined allocator would bake in whatever that allocator happens to
do, so it is sequenced after normalization deliberately.

## Outcome classification and adaptive presets

### D-140 Callers classify outcomes; the library never infers capacity pressure from generic failures

**Status:** Accepted, with open items · **Source:** Round-4 grooming

**Context.** Adaptive capacity is only safe if the controller knows what a failure
meant. A burst of caller-side validation errors is indistinguishable from
downstream collapse if all the library can see is "the function threw".

**Decision.** Callers classify each outcome as `Success`, `Throttled`,
`Overloaded`, `TransientFailure`, `CallerError`, or `Ignore`. `Throttled` and
`Overloaded` reduce capacity; `CallerError` has **no capacity effect**;
`TransientFailure` is neutral by default. With no classifier supplied, every
failure is treated as `TransientFailure`, so adaptation can reduce capacity only
from explicit signals — never from raw failure counts. Cancellation is never a
capacity signal. Classes are a bounded enum usable as a metric dimension, and
classification never alters the caller's own outcome.

**Consequences.** The decisive pair is `Throttled` versus `CallerError`: a
downstream 429 must reduce throughput, and a malformed payload must not. Without
it, a client sending bad input could drive a service to throttle itself. This is
why AWS's adaptive retry mode treats throttling as its own category.

### D-141 One outcome-classification vocabulary is shared with the retry predicate

**Status:** Accepted in principle, with open items · **Source:** Round-4 grooming

**Decision.** The classification vocabulary in
[D-140](#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures)
is the definition of an **"ordinary failure"** that
[D-011](#d-011-retrydecorator-retries-every-ordinary-failure-by-default) left open:
`TransientFailure`, `Throttled`, and `Overloaded` are retryable, `CallerError` is
not, and cancellation is terminal. One vocabulary shared by `RetryDecorator` and
`AdaptiveCapacityPolicy` is strongly preferred over two parallel taxonomies of
failure.

**Open.** Whether the two surfaces literally share a type, and whether the retry
predicate then becomes expressible as a classifier.

### D-142 Adaptive presets are opt-in and the congestion preset comes later

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** Presets are opt-in and never implicit; their presence in the library
is not consent to adapt. `DefaultOverclockPolicy` — demand-driven upward
adaptation — ships now as the built-in opt-in policy. A **congestion policy** —
pressure-driven downward adaptation when latency or failure pressure rises — is
accepted in direction and specified later.

**Consequences.** The two are complements: one finds spare capacity, the other
finds where a dependency starts degrading. Congestion control is the more broadly
useful of the two in production, as Netflix's concurrency-limits demonstrates, but
it is sequenced second because it needs outcome classification and a trustworthy
latency signal first. A congestion controller fed unclassified failures would
reduce capacity in response to caller errors — the exact outage it exists to
prevent.

## Provider capabilities

### D-150 Providers declare capabilities and insufficient providers fail configuration

**Status:** Accepted, with open items · **Source:** Round-4 grooming; resolves a prior open question

**Decision.** A provider **declares** its capabilities — atomic claim, leases and
TTL, membership, idempotent identity sets, authoritative coordination time,
configuration epoch, health and degradation signal. A controller **requires** a
named subset, and configuration **fails loudly at startup** when the two do not
match, naming the missing capability and the utility that required it. Declaration
is explicit and machine-checkable, never inferred from a backend's name. Partial
support is no support: "atomic except during failover" is not atomic. A provider
must never emulate a strict guarantee with eventual local guesses.

**Consequences.** `ThroughputController` cannot be coordinated without
authoritative coordination time, because pacing is a statement about *when*.
`GroupedRateController` needs a claim that checks the group limit and the global
limit **together**, so a provider offering only single-limit claims must be
rejected for grouped use even though it would serve a plain `RateController`. A
PostgreSQL provider that cannot express the grouped atomic claim is rejected at
startup instead of quietly degrading a tenant-isolation guarantee an operator
believes is enforced.

**Open.** Whether a capability can be declared at a *level* — "atomic claim,
single limit only" versus "multi-limit" — rather than as a boolean.

## Roadmap and scope

### D-160 Roadmap order: keyed registry, then shared job options, then supervision, then outcome classification

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** Build in this order:

1. **`KeyedControllerRegistry`** — one new core utility plus tests
   ([D-120](#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key)).
2. **Shared `JobOptions` plus deadline estimation** — the shared controller
   contract, advisory queries, and deadline-aware admission
   ([D-110](#d-110-a-shared-controller-contract-owns-submission-job-options-and-admission-queries)
   through [D-115](#d-115-deadline-aware-admission-rejects-at-submission-with-controller-bounded-accuracy)).
3. **Worker supervision**
   ([D-130](#d-130-worker-failure-behavior-is-an-explicit-enumerated-supervision-policy)).
4. **Outcome classification**
   ([D-140](#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures)).

Then, in no committed order: keyed-registry safeguards hardening, accumulator
flush controls
([D-131](#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown)),
adaptive presets
([D-142](#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later)),
grouped QoS shares
([D-132](#d-132-reserved-group-shares-are-accepted-in-direction-and-deferred-in-scope)),
and provider capability checks
([D-150](#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration)).

**Consequences.** The ordering is dependency-driven, not value-driven: the registry
needs the shared contract to be useful across controller types, outcome
classification needs to exist before a congestion preset can be trusted, and QoS
shares need the grouped normalization algorithm first.

### D-161 Explicitly out of scope

**Status:** Accepted · **Source:** Round-4 grooming

**Decision.** The following are deliberately not built, and a proposal to add one
must argue against this record:

| Not building | Why |
| --- | --- |
| Generic distributed payload or job queueing in the synchronization provider | The provider coordinates permission and shared state, never executable work. A durable transport is a different product with a different reliability contract ([D-163](#d-163-synchronizationprovider-is-the-backend-neutral-public-contract)) |
| Adaptive behavior on by default | Hidden adaptation is how limiters cause outages. It stays opt-in ([D-142](#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later)) |
| Unbounded completed-job history | Retaining every finished job ID forever is a memory leak with a reporting excuse. Retention is opt-in and bounded |
| A built-in metrics database | Core exposes raw events and snapshots; aggregation and storage belong to the user's stack ([D-090](#d-090-observability-is-event-driven-and-exposes-raw-data)) |
| Exactly-once execution promises for user functions | Unachievable without durable storage and idempotent user code, neither of which the library owns ([D-072](#d-072-job-persistence-across-restarts-is-out-of-scope)) |
| Framework-specific APIs in core | Go HTTP/gRPC and Rust Tower/Axum integrations ship as separate adapter packages, following the same zero-dependency rule as the OTel package ([D-091](#d-091-otel-is-a-separate-opt-in-package-per-language)) |

**Consequences.** Adapters are explicitly *not* rejected — only their presence in
core is. A Tower `ConcurrencyLimitLayer`-style adapter over `RateController` is a
welcome separate package.

### D-162 Limitful is the canonical project and library name

**Status:** Accepted · **Source:** User decision; supersedes [D-107](#d-107-working-name-is-limitee)

**Decision.** The canonical current name of the repository, project, library,
packages, documentation, examples, and future native bindings is **Limitful**.
New and maintained normative material uses `Limitful`.

**Consequences.** Historical material remains historical: the superseded D-107
record and the raw `Q&A-Round-3.md` transcript retain `Limitee` where that was the
name actually used. Preserving those references records provenance; it does not
create a current alias, compatibility promise, or unresolved naming question.

### D-163 SynchronizationProvider is the backend-neutral public contract

**Status:** Accepted · **Source:** User decision; supersedes [D-080](#d-080-in-memory-by-default-redis-is-opt-in), [D-081](#d-081-enabling-redis-coordinates-every-utility), and the controller-facing part of [D-085](#d-085-redis-access-goes-through-a-user-supplied-adapter)

**Decision.** `SynchronizationProvider` is the sole public cross-instance
coordination boundary. Controller and utility APIs depend on its semantic
operations and declared capabilities; they never name Redis, PostgreSQL, a client
library, raw commands, or a backend adapter. In-process operation remains the
zero-dependency default. Coordination is enabled explicitly per compatible
utility by injecting a provider; several utilities may share one provider
instance without making coordination process-wide or implicit.

A utility declares the capabilities it requires, and configuration fails before
work is accepted when the provider cannot supply them
([D-150](#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration)).
The provider coordinates permission and shared state, never executable payloads
or a durable job queue ([D-161](#d-161-explicitly-out-of-scope)).

**Consequences.** Backend packages implement this contract. The old statement
that "enabling Redis coordinates every utility" no longer defines the API or
activation model. A backend-specific adapter may still be injected into its
concrete provider, but it never appears in a controller constructor or contract.

### D-164 Redis coordination is a concrete provider under the neutral contract

**Status:** Accepted, with inherited open items · **Source:** User decision; clarifies [D-082](#d-082-distributed-counting-is-set-based-never-increment-or-decrement) through [D-087](#d-087-cluster-compliance-requires-deliberate-selective-slotting-and-a-user-prefix)

**Decision.** `RedisSynchronizationProvider` is a concrete implementation of
`SynchronizationProvider`, not a competing generic coordination subsystem. Its
technical design owns Redis-specific identity sets, commands/scripts, key
prefixes, hash-slot placement, heartbeat records, stale-member pruning, outage
detection, and recovery. Its user-supplied Redis adapter remains the backend test
and client-integration seam described by D-085.

D-083's fail-open rule is narrowed from a project-wide controller rule to the
Redis provider's **divided-allocation mode** when the owning utility has a finite
previously allocated local share and documents that degraded behavior. The
provider reports degradation; the utility owns the product-level choice and must
not label a local approximation as a hard global guarantee. Capabilities that
need atomic global claims or authoritative coordination time do not acquire a
generic fail-open promise from this record. In particular, unresolved
`ThroughputController` partition behavior remains unresolved.

**Consequences.** D-082 remains the Redis representation rule and the
backend-neutral idempotency requirement. D-084's frozen-membership behavior,
D-086's self-cleaning liveness protocol, and D-087's cluster slotting rules remain
valid Redis-provider mechanics. Their existing open choices remain open; this
record does not guess the non-frozen policy, allocation remainder algorithm,
multi-key layout, adapter interface, or timing defaults.

### D-165 ThroughputController spends time credits atomically at launch

**Status:** Accepted · **Source:** `throughput-controller.md`

**Decision.** `ThroughputController` is the time-based peer of
`RateController`. Cost is a positive immutable value evaluated once at
submission, defaults to `1`, and is spent exactly once at the atomic launch
commit. Completion, failure, and cancellation after commit do not refund it. A
cost that can never fit the configured maximum fails at submission rather than
waiting forever.

This record does not choose the simple API's pacing model, make fixed windows the
default, or decide whether weighted cost affects pacing as well as quota. Those
choices remain open in the owning utility document.

**Consequences.** The utility limits when work may start, not how many started
jobs remain in flight. A concurrency ceiling requires explicit composition with
`RateController`. Every retry attempt re-enters admission and spends its own
credit.

### D-166 ThroughputController uses one bounded event-driven scheduler

**Status:** Accepted · **Source:** `throughput-controller.md`

**Decision.** Each `ThroughputController` owns one bounded queue and one
event-driven scheduling loop with at most one armed wake-up for the earliest
known eligibility. It has no busy polling, timer per item, sleep per item, or
worker per queued job. User functions, policies, and event handlers run outside
the scheduler lock.

The controller follows the shared drain and cancel-pending lifecycle. Drain
continues to honor pacing and quota; cancel-pending announces every queued
non-execution; already-started work may finish. Ordered disposal releases timers,
subscriptions, provider reservations, and membership. Details already marked
open in the owning documents—such as drain escalation and awaiting-insertion
shutdown races—remain open.

### D-167 AdaptiveCapacityPolicy proposes; controllers validate and clamp

**Status:** Accepted · **Source:** `adaptive-capacity-policy.md`; complements [D-140](#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) through [D-142](#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later)

**Decision.** `AdaptiveCapacityPolicy` is an opt-in, reusable, pure policy
boundary. It receives immutable normalized inputs and proposes an effective
capacity plus a bounded reason code. The owning controller—not the policy—validates
freshness and numeric validity, clamps the proposal to its documented envelope,
applies hysteresis/dwell/cooldown, and commits the state transition.

Policy evaluation is synchronous, side-effect free, outside scheduling locks, and
never performs remote measurement. A throwing policy, stale/invalid signal, or
shutdown ends any overclock and returns to a safe controller-defined target
without failing queued work. Adaptation never raises a hard ceiling, manufactures
quota, accumulates unused headroom, or becomes enabled by the mere presence of
metrics.

### D-168 Probe retains the latest successful value with freshness metadata

**Status:** Accepted · **Source:** `probe.md`

**Decision.** `Probe<T>` periodically invokes a user measurement function and
publishes an immutable snapshot containing the latest successful value, success
and attempt times, latest failure, freshness, and a monotonically increasing
successful generation. A failed refresh updates failure metadata but never clears
or replaces the last-known-good value. Before the first success, `current()`
returns the language-idiomatic absence type, never a fabricated fallback.

The default history capacity is one and every configured history is bounded.
Probe reports data and freshness; callers decide what stale, unavailable, or
unhealthy means.

### D-169 Probe refreshes serially and coalesces missed intervals

**Status:** Accepted · **Source:** `probe.md`

**Decision.** A probe starts its first refresh immediately. At most one
measurement invocation is active for that probe. Later intervals begin after the
preceding refresh completes; a tick due during an active refresh is coalesced into
one subsequent refresh rather than overlapping or accumulating timers. The
measurement runs outside probe state synchronization, and publishing success or
failure is one atomic snapshot transition.

Refresh uses an injectable monotonic clock/scheduler and cooperative
cancellation/timeout; the default refresh timeout equals the interval.

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

**Status:** Rejected for Redis divided-allocation mode by [D-083](#d-083-a-redis-outage-fails-open-to-local-continuation); scope clarified by [D-164](#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)

Stop admitting work during a Redis outage to preserve the global ceiling exactly.
Rejected: Redis must never be a dependency whose outage disables the application.
Bounded overshoot is the accepted price.

### S-009 Minimum job spacing is not a goal

**Status:** Superseded by [D-001](#d-001-ratecontroller-limits-by-concurrency-not-by-time-window) and `ThroughputController`

The original scope said Limitful implements a subset of Bottleneck in which
"minimum job spacing is not a goal". That remains true **of `RateController`**,
which is still purely a concurrency limiter. It is no longer true of the library:
[`ThroughputController`](./utilities/throughput-controller.md) offers optional
`minimumStartSpacing` and smooth pacing as an explicit traffic-shaping choice. The
capability moved to a separate utility rather than being abandoned.

### S-010 A per-second limiter is merely under consideration

**Status:** Superseded — now built as `ThroughputController`

Earlier rounds listed "a separate per-second rate limiter" as an open item that
was explicitly *not* `RateController`. That question is resolved: the utility
exists as [`ThroughputController`](./utilities/throughput-controller.md), a peer of
`RateController` under the shared controller contract
([D-110](#d-110-a-shared-controller-contract-owns-submission-job-options-and-admission-queries)),
with its own pacing, quota, cost, and adaptive-policy design. The two remain
deliberately separate utilities: one bounds work in flight, the other bounds when
work may start.

## Unresolved items

Every open question in one place. Each is owned by a document that will record the
answer. **A blocked test case must never be implemented by guessing**
([testing.md § Cross-language parity](./testing.md#cross-language-parity-process)).

| Area | Question | Owner | Origin |
| --- | --- | --- | --- |
| ~~Rate limiting~~ | ~~Whether a separate per-second rate limiter utility is built~~ **Resolved: `ThroughputController`** | [S-010](#s-010-a-per-second-limiter-is-merely-under-consideration) | `CLAUDE.md` |
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
| ~~Redis~~ | ~~Whether coordination is per-utility or process-wide~~ **Resolved: explicitly enabled per compatible utility by [D-163](#d-163-synchronizationprovider-is-the-backend-neutral-public-contract), never process-wide or implicit** | [redis-coordination.md](./subsystems/redis-coordination.md#open-items) | Consolidation |
| Observability | Event payload shapes, delivery synchronicity, ordering guarantees | [observability.md](./subsystems/observability.md#open-items) | Consolidation |
| Observability | OTel metric and span naming conventions | [observability.md](./subsystems/observability.md#open-items) | Consolidation |
| Project | Which binding lands first, and per-language test tooling | [testing.md](./testing.md#open-items) | Consolidation |
| Docs | The docs site's tooling, hosting, structure, and Replit playground contents | [D-109](#d-109-a-docs-site-with-per-utility-examples-and-a-playground-is-a-deliverable) | `CLAUDE.md` § Notes |
| Controller contract | Whether `RetryDecorator`'s three priority modes collapse into `JobOptions.priority`, and where probabilistic prioritization then lives | [controller-contract.md](./subsystems/controller-contract.md#open-items) | Round 4 |
| Controller contract | The bounded-starvation rule that would unblock weighted concurrency cost | [controller-contract.md](./subsystems/controller-contract.md#open-items) | Round 4 |
| Controller contract | Priority band count, and whether aging or weighted-fair is the advanced default | [controller-contract.md](./subsystems/controller-contract.md#open-items) | Round 4 |
| Controller contract | Whether `estimatedStartAt` accepts a caller-supplied duration estimator | [controller-contract.md](./subsystems/controller-contract.md#open-items) | Round 4 |
| Controller contract | Whether the shared contract is a language interface or only a documented shape in Go and Rust | [controller-contract.md](./subsystems/controller-contract.md#open-items) | Round 4 |
| Keyed registry | Whether `globalCeiling` is mandatory rather than recommended | [keyed-controller-registry-draft.md](./utilities/keyed-controller-registry-draft.md#open-items) | Round 4 |
| Keyed registry | Whether idle TTL runs from last submission or from the moment the controller became empty | [keyed-controller-registry-draft.md](./utilities/keyed-controller-registry-draft.md#open-items) | Round 4 |
| Keyed registry | Eviction selection among several evictable keys, and whether eviction may be preemptive | [keyed-controller-registry-draft.md](./utilities/keyed-controller-registry-draft.md#open-items) | Round 4 |
| Keyed registry | Whether per-key cross-instance scopes are affordable at 10,000 keys | [keyed-controller-registry-draft.md](./utilities/keyed-controller-registry-draft.md#open-items) | Round 4 |
| Workers | Replacement backoff default, and whether repeated replacement failures escalate to `Stop controller` | [parallel-workers.md](./utilities/parallel-workers.md#open-items) | Round 4 |
| Adaptive | Whether `RetryDecorator` and the adaptive policy share one outcome-classification type | [adaptive-capacity-policy.md](./utilities/adaptive-capacity-policy.md#open-items) | Round 4 |
| Adaptive | The congestion preset's algorithm and latency-signal source | [adaptive-capacity-policy.md](./utilities/adaptive-capacity-policy.md#open-items) | Round 4 |
| Adaptive | Whether the 80/20 safety-pressure guidance is a default or only documentation | [adaptive-capacity-policy.md](./utilities/adaptive-capacity-policy.md#open-items) | Round 4 |
| Grouped | Reserved-share allocation, pending the normalization algorithm | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md#open-items) | Round 4 |
| Provider | Whether capabilities are booleans or declared at a level | [synchronization-provider.md](./utilities/synchronization-provider.md#open-design-questions) | Round 4 |
