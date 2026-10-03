# Architecture

Limitee is a set of small load-leveling utilities that compose. Each utility owns
one concern, exposes raw events and metrics, and accepts user functions for every
policy decision. There is no central scheduler, no god object, and no shared
mutable registry.

- [Layering](#layering)
- [Component boundaries](#component-boundaries)
- [Invariants](#invariants)
- [Admission and concurrency flow](#admission-and-concurrency-flow)
- [Composition guidance](#composition-guidance)
- [Lifecycle and disposal](#lifecycle-and-disposal)
- [Distributed mode](#distributed-mode)
- [Observability seams](#observability-seams)
- [Implementation strategy](#implementation-strategy)
- [Open items](#open-items)

## Layering

Two primitives sit at the bottom — a bounded queue with an admission policy, and
a worker pool whose size is sampled from a user function. Every other utility is
built from them. `RetryDecorator` is the exception: it is a pure function wrapper
that composes *around* the others and depends on none of them.

```mermaid
flowchart TD
  subgraph Caller["Caller code"]
    UF["User function"]
    UBF["User batch function"]
  end

  subgraph Wrappers["Function decorators"]
    RD["RetryDecorator"]
  end

  subgraph Utilities["Utilities"]
    RC["RateController"]
    GRC["GroupedRateController"]
    AA["AsyncAccumulator"]
    WAA["WeightedAsyncAccumulator"]
  end

  subgraph Primitives["Core primitives"]
    PW["ParallelWorkers"]
    BQ["Bounded queue and admission"]
    CLK["Clock and scheduler"]
  end

  subgraph Coordination["Optional coordination"]
    TRK["Distributed tracker"]
    ADP["User-supplied Redis adapter"]
  end

  subgraph Observability["Observability"]
    EV["Events and metrics snapshots"]
    OTEL["Optional OTel package"]
  end

  UF --> RD
  UF --> RC
  UBF --> AA
  UBF --> WAA

  RD -->|"wraps any function, including an already-limited one"| RC
  GRC --> RC
  RC --> PW
  RC --> BQ
  AA --> PW
  AA --> BQ
  WAA --> AA
  PW --> CLK
  BQ --> CLK
  RD --> CLK

  RC -.->|"when enabled"| TRK
  GRC -.->|"when enabled"| TRK
  AA -.->|"when enabled"| TRK
  PW -.->|"when enabled"| TRK
  TRK --> ADP

  RC --> EV
  GRC --> EV
  AA --> EV
  WAA --> EV
  PW --> EV
  RD --> EV
  EV -.->|"separate opt-in package"| OTEL
```

Dotted edges are optional and absent by default: in-process, in-memory, zero
dependencies ([D-080](./decisions.md#d-080-in-memory-by-default-redis-is-opt-in)).

### Why `WeightedAsyncAccumulator` sits on `AsyncAccumulator`

It is the same utility with one extra admission rule: a stored per-item weight
instead of an item count governs when a batch closes. Everything else — timeout
stages, outcome correlation, batching-worker lifecycle — is inherited unchanged.
See [weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md).

### Why `RateController` sits on `ParallelWorkers`

`RateController` needs "run up to N things at once, pulling from a queue as slots
free". That is exactly a worker pool whose size can change. `RateController`
contributes the hard ceiling and the queue; `ParallelWorkers` contributes the
worker loop, the sampling-driven resize, and graceful worker drain.

The worker count never raises the ceiling. It only **divides a fixed budget**
([INV-4](#invariants), [D-002](./decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling)).

## Component boundaries

| Component | Owns | Explicitly does not own |
| --- | --- | --- |
| [Bounded queue and admission](./subsystems/queue-and-admission.md) | Capacity bound, overflow policy, admission waiting, pre-admission and queue-wait timeouts, cancellation-before-start | Execution, retries, batching |
| [ParallelWorkers](./utilities/parallel-workers.md) | Worker lifecycle, sampled worker count, scaling delta, graceful drain, worker events | Queue capacity, global ceilings, what the work is |
| [RateController](./utilities/rate-controller.md) | The hard in-flight ceiling `N`, queueing of submitted jobs, failure isolation, rate metrics | Retries ([D-004](./decisions.md#d-004-ratecontroller-never-retries)), time-window limiting ([D-001](./decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window)), batching |
| [GroupedRateController](./utilities/grouped-rate-controller.md) | Static group definitions, group matching, per-group limits, shared-ceiling arbitration | Dynamic group creation, per-group retry policy |
| [AsyncAccumulator](./utilities/async-accumulator.md) | Batch accumulation, batching-worker loop, outcome correlation, the three timeout stages | Rate limiting ([D-041](./decisions.md#d-041-asyncaccumulator-does-not-integrate-with-ratecontroller)), retrying a failed batch |
| [WeightedAsyncAccumulator](./utilities/weighted-async-accumulator.md) | Weight computation at insertion, weight-budget admission, strict/flexible over-max policy | Anything already owned by `AsyncAccumulator` |
| [RetryDecorator](./utilities/retry-decorator.md) | Attempt budget, backoff, retry predicate, attempt hooks, aggregated error, deferred retry queue | Concurrency, queueing, batching — it holds no slot while waiting ([INV-6](#invariants)) |
| [Distributed tracker](./subsystems/redis-coordination.md) | Set-based membership and counting, liveness, fail-open fallback, key slotting | Connecting to Redis — the user injects an adapter ([D-085](./decisions.md#d-085-redis-access-goes-through-a-user-supplied-adapter)) |
| [Observability](./subsystems/observability.md) | Raw events, metrics snapshots, sampling event | Opinionated telemetry — OTel lives in a separate opt-in package ([D-091](./decisions.md#d-091-otel-is-a-separate-opt-in-package-per-language)) |

### Dependency rules

1. A utility may depend on a primitive. A primitive never depends on a utility.
2. Core packages never depend on OpenTelemetry, a Redis client, or any logger.
3. `RetryDecorator` depends on no other utility. Any apparent coupling (a retry
   re-entering admission) happens because the *caller* composed the two, not
   because the types know about each other.
4. Cross-utility behavior is the caller's composition, never implicit wiring.

## Invariants

These hold in every language. A change to any of them is a specification change
([docs/README.md § How to change a documented behavior](./README.md#how-to-change-a-documented-behavior)).

| ID | Invariant |
| --- | --- |
| **INV-1** | A queued job is never dropped unannounced, and never by dropping the oldest. |
| **INV-2** | The only ways a queued job leaves without executing are announced to the caller: cancel-pending shutdown, an expired queue-wait timeout, or cancellation of the job's own task. |
| **INV-3** | Every internal queue is bounded, with a configurable capacity, timeout set, and overflow strategy. |
| **INV-4** | During coordinated operation, the configured `N` is the hard global in-flight ceiling. A sampled worker count only divides that budget and is clamped to `N`. The sole exception is Redis fail-open ([INV-11](#invariants)). |
| **INV-5** | Cancellation is terminal. It is never retried and never overridden by a user predicate. |
| **INV-6** | A retrying job holds no concurrency slot while waiting between attempts. |
| **INV-7** | An item that has timed out while queued, or whose task was cancelled, never executes later — it is removed, not merely abandoned by its caller. |
| **INV-8** | A worker marked dead is never revived. Capacity returns by starting a fresh worker. |
| **INV-9** | A batch never exceeds its maximum weight. The single exception is one over-max item admitted in flexible mode, which runs alone. |
| **INV-10** | Once shutdown begins, new enqueues fail immediately with cancellation. |
| **INV-11** | Distributed counting is set-based and idempotent: entities add and remove their own ID, and the count is set cardinality. Increment/decrement is never used. |
| **INV-12** | A failing task is isolated to itself. Queue, workers, and sibling tasks continue. |
| **INV-13** | Observable behavior is identical across languages. Only the API surface differs. |
| **INV-14** | No job state survives process exit. Durable queues are out of scope; the reliability guarantee is process-lifetime only. |

## Admission and concurrency flow

The path a submitted job takes, with the group layer shown where it applies. The
same shape serves `RateController` (one implicit group) and
`GroupedRateController` (many).

```mermaid
flowchart TD
  SUB["Caller submits a job"] --> SHUT{"Shutdown started?"}
  SHUT -->|"yes"| FAILSHUT["Fail with cancellation - INV-10"]
  SHUT -->|"no"| MATCH{"Grouped?"}

  MATCH -->|"no"| CAP
  MATCH -->|"yes"| PRED["Evaluate group predicates in order"]
  PRED --> HIT{"A group matched?"}
  HIT -->|"yes"| CAP
  HIT -->|"no"| DEF{"Default group enabled?"}
  DEF -->|"yes"| CAP
  DEF -->|"no"| THROW["Throw - unmatched item"]

  CAP{"Queue below capacity?"} -->|"yes"| ENQ["Enqueue"]
  CAP -->|"no"| OVF{"Overflow policy"}
  OVF -->|"reject - default"| FAILFULL["Fail immediately"]
  OVF -->|"await insertion - advanced"| WAIT["Wait outside the queue, uncapped, no FIFO guarantee"]
  WAIT -->|"space freed"| ENQ
  WAIT -->|"cancelled"| REMOVED["Removed, guaranteed never to enter - INV-7"]

  ENQ --> PICK["A worker becomes free"]
  PICK --> QWT{"Queue-wait timeout expired, or task cancelled?"}
  QWT -->|"yes"| DROP["Remove and report timeout or cancellation - INV-2, INV-7"]
  QWT -->|"no"| SLOT{"Slot available under the ceiling?"}

  SLOT -->|"grouped"| GCHK{"Group limit and shared ceiling both allow?"}
  GCHK -->|"no"| ROT["Fair rotation picks another competing group"]
  ROT --> PICK
  GCHK -->|"yes"| RUN
  SLOT -->|"ungrouped"| RUN["Acquire slot and execute"]

  RUN --> DONE{"Outcome"}
  DONE -->|"success"| REL["Release slot, emit item complete"]
  DONE -->|"failure"| ERR["Release slot, emit error, isolate - INV-12"]
```

Slot accounting is the only place the ceiling is enforced, and it is enforced on
acquisition, never by trusting the worker count
([D-002](./decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling)).

## Composition guidance

Limitee composes by wrapping functions, not by registering components with each
other. The caller decides the order, and the order is meaningful.

> Illustrative pseudocode. No public API signature is committed yet.

### Retry outside the limiter — the common case

```text
limited = rateController.wrap(callApi)
resilient = retry.wrap(limited, { attempts: 3 })
```

Each attempt re-enters admission and acquires its own slot; the backoff happens
outside the limiter, holding nothing
([INV-6](#invariants), [D-015](./decisions.md#d-015-awaited-retries-re-enter-normal-admission)).
This is the recommended order: a saturated downstream service sees at most `N`
concurrent calls including retries.

```mermaid
sequenceDiagram
  autonumber
  participant C as Caller
  participant R as RetryDecorator
  participant A as Admission and ceiling
  participant W as Worker
  participant S as Downstream service

  C->>R: invoke
  R->>A: attempt 1 - request admission
  A->>W: slot acquired
  W->>S: call
  S--xW: failure
  W->>A: release slot
  A-->>R: failure surfaced
  Note over R,A: Backoff happens here, holding no slot - INV-6
  R->>A: attempt 2 - request admission again
  A->>W: new slot acquired
  W->>S: call
  S-->>W: success
  W->>A: release slot
  A-->>R: success
  R-->>C: success
```

### Retry inside the limiter — rarely what you want

```text
resilient = retry.wrap(callApi)
limited = rateController.wrap(resilient)
```

One logical job occupies one slot across every attempt *and* every backoff,
because the limiter cannot see inside the wrapped function. This starves the
queue. Use it only when a slot must represent a whole logical operation.

### Batching plus limiting

`AsyncAccumulator` deliberately does not know about `RateController`
([D-041](./decisions.md#d-041-asyncaccumulator-does-not-integrate-with-ratecontroller)).
The caller picks the composition:

```text
# Limit how many batches run concurrently
limitedBatchFn = rateController.wrap(myBatchFn)
accumulator    = asyncAccumulator(limitedBatchFn, { maxBatchSize: 50 })

# Or limit submissions into the accumulator
limitedSubmit = rateController.wrap(item => accumulator.submit(item))
```

### Grouping plus batching

A `GroupedRateController` in front of per-group accumulators gives per-tenant
batching under one global ceiling. Keep the group predicate pure and cheap: it
runs on every submission.

### Compositions to avoid

| Anti-composition | Why |
| --- | --- |
| Expecting `RateController` to retry | It never does ([D-004](./decisions.md#d-004-ratecontroller-never-retries)). Wrap with `RetryDecorator`. |
| Nesting a limiter inside its own job function | The inner acquisition can only wait on slots the outer call is holding. |
| Unbounded `await insertion` with no upstream control | Limitee does not cap admission waiters; that memory is the caller's problem ([D-032](./decisions.md#d-032-admission-waiters-are-uncapped-and-the-callers-responsibility)). |
| A heavy weight function or group predicate | Both run on the submission path. Weight is computed once at insertion ([D-052](./decisions.md#d-052-item-weight-is-computed-once-at-insertion)); predicates have no such cache. |

## Lifecycle and disposal

Every utility follows the same four-state lifecycle. Disposal is explicit and
always completes the chosen shutdown mode before tearing down
([D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending)).

```mermaid
stateDiagram-v2
  [*] --> Created
  Created --> Running: first submission or start
  Running --> Running: sample, scale, execute

  Running --> Draining: shutdown with drain
  Running --> Cancelling: shutdown with cancel pending

  state Draining {
    [*] --> RefuseNew
    RefuseNew --> FinishQueued: queued work continues
    FinishQueued --> WorkersStopped: workers drain, never cancelled mid-task
  }

  state Cancelling {
    [*] --> RefuseNew2
    RefuseNew2 --> CancelQueued: queued-but-not-started jobs complete as cancelled
    CancelQueued --> AwaitInFlight: already-executing jobs are not cancelled
    AwaitInFlight --> WorkersStopped2: workers drain
  }

  Draining --> Disposed: resources released
  Cancelling --> Disposed: resources released
  Disposed --> [*]

  note right of Created
    No background work before the first use
  end note
  note right of Disposed
    Terminal. Enqueue attempts after shutdown
    begins fail with cancellation - INV-10
  end note
```

Rules that hold in both shutdown modes:

1. **New enqueues stop immediately** and fail with cancellation
   ([INV-10](#invariants)).
2. **Workers are never cancelled mid-task.** A stopping worker stops reading from
   the queue, finishes its current item, and disappears
   ([D-022](./decisions.md#d-022-workers-drain-gracefully-and-are-never-revived)).
3. **Already-executing jobs are not cancelled** by cancel-pending mode. They may
   finish under their normal behavior.
4. **Cancel-pending is the announced exception to [INV-1](#invariants).** Queued
   jobs that never started complete as cancelled, visibly to their callers.
5. **Disposal is ordered:** refuse new work → settle queued work per mode → drain
   workers → stop the heartbeat and distributed membership (graceful removal, see
   [redis-coordination.md](./subsystems/redis-coordination.md)) → release
   resources.
6. **Nothing survives the process** ([INV-14](#invariants)). Durable queues are
   out of scope; a caller who needs them layers their own store in front.

**Open item.** What happens to callers already *awaiting insertion* when shutdown
begins is not specified ([D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending)).

## Distributed mode

By default Limitee is in-process and in-memory. Enabling the optional distributed
tracker makes *everything* coordinated — `RateController` concurrency,
`ParallelWorkers` counts, and the accumulators
([D-081](./decisions.md#d-081-enabling-redis-coordinates-every-utility)).

The architectural commitment is that coordination is **advisory, never
load-bearing for availability**: a Redis outage degrades accuracy, never
liveness.

```mermaid
flowchart LR
  subgraph P1["Process A"]
    RCA["RateController"] --> TA["Tracker"]
  end
  subgraph P2["Process B"]
    RCB["RateController"] --> TB["Tracker"]
  end
  TA --> ADP1["User adapter"] --> REDIS[("Redis cluster")]
  TB --> ADP2["User adapter"] --> REDIS
  REDIS -->|"set cardinality, sampled about once per minute"| TA
  REDIS -->|"set cardinality, sampled about once per minute"| TB
```

Details — set-based counting, the liveness protocol, fail-open behavior, frozen
membership, and cluster key slotting — live in
[redis-coordination.md](./subsystems/redis-coordination.md).

## Observability seams

Each utility emits raw events and exposes a metrics snapshot; nothing is
aggregated or formatted for the user
([D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data)).
The seams are fixed so the optional OTel package can wrap them without the core
knowing it exists:

- **Events** — worker start/stop/complete, worker-count change, item complete,
  error, batch exceeded, max batch, and a periodic sample event.
- **Snapshots** — immutable, point-in-time reads of queue depth, in-flight count,
  worker count, and rate statistics.
- **Spans** — the optional package injects a few library-stage spans (admission
  wait, batch size, which batch) so slowness can be attributed to Limitee rather
  than to user code, while the user's own spans still dominate the trace.

See [observability.md](./subsystems/observability.md).

## Implementation strategy

**Full native reimplementation per language.** Targets share the design and the
business test spec, never code. There is no shared Rust core with thin bindings
([D-100](./decisions.md#d-100-native-reimplementation-per-language-no-shared-core)).

Rationale:

1. **No FFI marshalling.** A shared core forces a boundary crossing per
   operation; for operations this cheap, the crossing can cost more than the work.
2. **User functions are first-class.** The entire API accepts user callbacks;
   passing functions across an FFI boundary is painful and is avoided.
3. **The shared-core benefit is correctness, not speed** — writing the tricky
   logic once. Here that is outweighed by nativeness and flexibility, and is
   recovered instead through the shared business test spec
   ([testing.md](./testing.md)).

Consequences each binding must accept:

- The shared Markdown test spec is the parity mechanism. A binding is complete
  when it satisfies the test matrix, not when its code resembles another binding.
- Surfaces are idiomatic per language — `async`/`await` in C# and TypeScript,
  idiomatic futures in Rust, channels and contexts in Go, idiomatic Python
  ([D-101](./decisions.md#d-101-api-surfaces-are-idiomatic-per-language)).
- Degree of parallelism is language-constrained (a single-threaded runtime cannot
  truly parallelize CPU work). **Semantics stay identical**; only achievable
  concurrency differs. This is a technical-test concern, not a business-test one
  ([testing.md § Technical tests](./testing.md#technical-tests)).
- C# and Rust bindings use functional constructs and current language features:
  records, immutable data, discriminated-union-style results, exhaustive matching.

## Open items

Architecture-level questions that remain open. The full list, including
utility-level items, is in [decisions.md § Unresolved](./decisions.md#unresolved-items).

| Item | Owner document |
| --- | --- |
| Disposition of callers awaiting insertion when shutdown begins | [queue-and-admission.md](./subsystems/queue-and-admission.md) |
| Which utilities inherit reject-by-default, uncapped waiters, and waiter ordering | [queue-and-admission.md](./subsystems/queue-and-admission.md) |
| Whether `GroupedRateController` is one shared admission layer or one `RateController` per group plus an arbitrator | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md) |
| Shared-capacity normalization and integer-remainder algorithm | [grouped-rate-controller.md](./utilities/grouped-rate-controller.md) |
| Non-frozen membership policy during a Redis outage | [redis-coordination.md](./subsystems/redis-coordination.md) |
| Whether the membership set and last-seen key share a hash tag | [redis-coordination.md](./subsystems/redis-coordination.md) |
| Whether a separate per-second rate limiter utility exists at all | [rate-controller.md](./utilities/rate-controller.md) |
| Library name: `Limitee` is the recorded decision; this repository directory is `Limitful` | [decisions.md](./decisions.md#d-107-working-name-is-limitee) |
