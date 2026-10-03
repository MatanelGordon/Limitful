# ParallelWorkers

**Responsibility.** Run a recurring task across a dynamically adjusted number of
concurrent workers, where the desired worker count comes from a user-supplied
sampling function.

`ParallelWorkers` is a core primitive. `RateController` and the accumulators are
both built on it.

- [Scope](#scope)
- [Public behavior](#public-behavior)
- [JavaScript worker-thread execution](#javascript-worker-thread-execution)
- [JavaScript prior art](#javascript-prior-art)
- [Worker lifecycle](#worker-lifecycle)
- [Sampling and scaling](#sampling-and-scaling)
- [Defaults](#defaults)
- [Advanced options](#advanced-options)
- [Lifecycle, cancellation, and timeouts](#lifecycle-cancellation-and-timeouts)
- [Composition](#composition)
- [Invariants](#invariants)
- [Events and metrics](#events-and-metrics)
- [Test coverage](#test-coverage)
- [Open items](#open-items)

## Scope

| Owns | Does not own |
| --- | --- |
| Worker creation, drain, and teardown | Queue capacity or overflow policy |
| The sampled desired worker count and clamping | Global concurrency ceilings — the owner clamps ([INV-4](../architecture.md#invariants)) |
| Scaling delta per sampling interval | What the work is |
| Task distribution across workers | Retries ([retry-decorator.md](./retry-decorator.md)) |
| Per-work-item error reporting | Worker-loop supervision or replacement |

It is useful on its own for maximizing CPU utilization and throughput in
high-concurrency environments, not only as an internal building block.

## Public behavior

> Illustrative pseudocode. No public API signature is committed yet.

```text
workers = parallelWorkers({
  work: async ctx => { item = await queue.take(ctx); await handle(item) },
  minWorkers: 1,
  maxWorkers: 16,
  sample: ctx => ctx.queueDepth > 1000 ? 16 : 4,
  sampleInterval: seconds(5),
})
```

Each worker runs a long-lived loop: take work, do work, repeat. Workers are
interchangeable; distribution is "whichever worker is free takes the next item",
not a partitioned assignment.

## JavaScript worker-thread execution

The JavaScript binding's parallel execution mode uses Node.js worker threads or
browser Web Workers. The pool manager owns scheduling, scaling, lifecycle,
metrics, cancellation, and result correlation; a worker owns execution of one
configured task. This gives CPU-bound JavaScript real parallelism without making
every caller manage a worker pool.

### Worker tasks are modules, not closures

An arbitrary JavaScript callback cannot cross into a worker: a worker has a
separate JavaScript environment, module cache, and heap. A task is therefore a
worker-loadable module plus a named exported handler. Its inputs and outputs must
cross the boundary as serializable values. The pool returns each result to the
submission that caused it; completion events and metrics supplement that result,
not replace it.

The task module may import its normal dependencies. Each worker loads that module
and its dependency graph once at startup, then reuses the loaded handler for many
jobs. Modules and normal in-memory objects are private to each worker; only
explicit messages, transferred buffers, or shared raw memory cross the boundary.

This keeps the simple experience honest: callers define a task, wrap it with a
pool, and submit serializable inputs. The pool owns the difficult parts—worker
creation, dispatch, delay, scaling, cancellation, metrics, and returning results.

### Packaging by environment

| Environment | Task packaging rule |
| --- | --- |
| Plain Node.js / TypeScript | Compile the task module with the application. The worker loads its compiled entry module through Node's normal module loader; Docker images ship that output and its ordinary dependencies. No runtime TypeScript compiler, virtual file system, or `eval` is required. |
| Browser / React | An environment adapter gives the bundler a worker entry module. The bundler emits the task's dependency graph using its normal worker support. |
| Optional tooling | A future first-party CLI or bundler plugin may generate task entries and manifests from marked exports. It is ergonomic sugar, not a requirement of the core API. |

The core API must not promise extraction of arbitrary inline callbacks. In
particular, a closure that captures local variables cannot be made worker-loadable
without changing those captured values into explicit task input or state.

### State snapshots and custom control messages

Workers must not read `window`, process globals, or mutable module state as if it
were shared. Instead, a caller may provide a state-reader function in the owning
JavaScript environment. Limitful invokes it, serializes its result, and sends a
versioned state snapshot through the pool's control channel to each worker.

Each task receives the latest snapshot that its worker has applied in its execution
context. State updates apply **between jobs**, never by mutating the context of a
running task. For a job that requires the exact latest state, the manager sends a
fresh snapshot with that job; this explicit consistency option costs an additional
state read and message.

The same control channel carries user-defined serializable events, configuration
updates, cancellation, progress, and results. Shared memory is an advanced option
for large, high-frequency raw data only; it cannot contain functions, closures,
classes, or ordinary JavaScript module state.

### Performance boundary

Worker-thread execution is for CPU-bound task bodies. It does not improve ordinary
asynchronous I/O, and tiny tasks can cost more in serialization and messaging than
they gain from parallel execution. The pool therefore keeps task code loaded per
worker and sends only job data and state updates at runtime. Rust or WebAssembly
may accelerate CPU-heavy algorithms within a task, but they do not make arbitrary
JavaScript callbacks transferable or parallel by themselves.

## JavaScript prior art

These libraries are **references for API and lifecycle design**, not required
Limitful dependencies. Their trade-offs are useful evidence for the JavaScript
binding's worker-task boundary.

| Library | What to study | Relevance to Limitful |
| --- | --- | --- |
| [Piscina](https://github.com/piscinajs/piscina) | Node worker-thread pools, module-backed default and named handlers, promise results, cancellation, backpressure, pool timing, and broadcast messages | The closest Node reference. Its separate worker-module and returned-result model validates Limitful's task descriptor, while Limitful retains its own portable lifecycle contract. |
| [Comlink](https://github.com/GoogleChromeLabs/comlink) | RPC over `postMessage`, proxy-shaped remote APIs, and transferable-value handling | A browser-focused reference for the control channel: state updates, progress, and custom messages should feel like deliberate asynchronous RPC, not ad-hoc event plumbing. It is not a worker pool. |
| [workerpool](https://github.com/josdejong/workerpool) | One pool abstraction across Node and browsers, explicit worker scripts, task execution, and embedded-worker trade-offs | Useful for comparing a cross-runtime surface. Its dynamic and embedded-worker options demonstrate convenience paths that Limitful must keep separate from the reliable module-task contract. |
| [@koale/useworker](https://useworker.js.org/) | React hook ergonomics: a function that runs in a worker plus status and termination controls | Likely the hook considered during design. Its simple hook/controller shape is good UI inspiration, but its pure-function and dependency constraints reinforce why Limitful's core cannot promise arbitrary closure extraction. |

When designing the JavaScript surface, prefer the durable lessons shared by these
libraries: explicit task identity, promise-correlated results, bounded queues,
clear cancellation/lifecycle, and a first-class control channel. Do not inherit
their environment-specific packaging mechanisms into the cross-language core.

## Worker lifecycle

A worker moves through explicit states. There is no transition back from
`Dead` — **a worker marked dead is never revived**
([D-022](../decisions.md#d-022-workers-drain-gracefully-and-are-never-revived),
[INV-8](../architecture.md#invariants)). If capacity is needed again, a *fresh*
worker is started. Kill and recreate, never resurrect — this keeps the state
machine simple.

```mermaid
stateDiagram-v2
  [*] --> Starting: scale up decision
  Starting --> Idle: OnWorkerStart emitted
  Idle --> Working: took an item
  Working --> Idle: OnTaskComplete emitted
  Working --> Faulted: task threw

  Faulted --> Idle: failure isolated, worker keeps looping

  Idle --> Draining: scale down decision
  Working --> Draining: scale down decision

  state Draining {
    [*] --> StopReading
    StopReading --> FinishCurrent: never cancelled mid-task
    FinishCurrent --> [*]
  }

  Draining --> Dead: OnWorkerStop emitted
  Dead --> [*]

  note right of Draining
    Patience: a retiring worker stops reading
    new items, finishes its current task,
    and only then disappears
  end note
  note right of Dead
    Terminal. Capacity returns only by
    starting a fresh worker - INV-8
  end note
```

**Patience with dying workers** is a hard rule: a worker selected for removal
stops reading more items from the queue, finishes the task in hand, and only then
disappears. It is never cancelled mid-work.

**Work-item failure is isolated:** the worker catches it, emits the error event,
and continues looping ([INV-12](../architecture.md#invariants)). A worker loop is
an internal protected `try`/`catch`/`finally` mechanism and is not expected to
escape or die. Consequently Parallel Workers exposes no worker-supervision,
replacement, backoff, or stop-on-worker-failure API ([D-176](../decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure)).

Outcome classification remains separate from work-item handling: for example, a
downstream `429` may guide an adaptive policy without terminating a worker.

## Sampling and scaling

The number of active workers is decided by a **user-supplied sampling function**
evaluated on a configurable interval
([D-020](../decisions.md#d-020-worker-count-comes-from-a-user-sampling-function)).
The function receives a context of metrics and data and returns the desired number
of active workers at that moment.

When a sampler is configured, it runs **immediately when the worker pool first
starts** by default, before the first sampling interval elapses
([D-170](../decisions.md#d-170-parallelworkers-makes-startup-sampling-configurable)).
Callers may instead defer the first sample until after one full interval. The
recurring schedule begins from the initial evaluation in either mode.

```mermaid
flowchart LR
  TICK["Sampling interval elapses"] --> CTX["Build context: metrics, queue depth, errors, current count"]
  CTX --> FN["Call the user sampling function"]
  FN --> DESIRED["Desired worker count"]
  DESIRED --> CLAMP["Clamp to min, max, and the owner's ceiling"]
  CLAMP --> DELTA["Limit the change to the scaling delta"]
  DELTA --> CMP{"Compare with current count"}
  CMP -->|"more needed"| UP["Start fresh workers"]
  CMP -->|"fewer needed"| DOWN["Mark workers for graceful drain"]
  CMP -->|"equal"| NOOP["No change"]
  UP --> EV["Emit worker-count change"]
  DOWN --> EV
```

**Scaling cap.** By default the worker count changes by **one at a time per
sample** — analogous to Kubernetes scaling pods one at a time. The user may
optionally define a **max delta**: the maximum number of worker changes, adding
or retiring, allowed per sampling interval
([D-021](../decisions.md#d-021-worker-count-changes-by-one-per-sample-by-default)).

**Clamping is the owner's job.** When `ParallelWorkers` runs inside
`RateController`, the sampled count is clamped so that total allowed in-flight
work never exceeds `N`
([D-002](../decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling)). The
sampler divides a fixed budget; it never enlarges it.

**Sampling pauses during a resize.** While a scale-up or graceful scale-down is
still transitioning the worker count, scheduled sampling ticks are skipped rather
than evaluated or queued ([D-171](../decisions.md#d-171-parallelworkers-skips-sampling-during-worker-count-transitions)). Once the
transition settles, the next regular tick may sample again. This prevents
overlapping decisions from acting on a count that has not yet become real.

## Defaults

| Option | Default | Notes |
| --- | --- | --- |
| `work` | **Required** | The loop body |
| Min workers | 1 | The pool never scales itself to zero ([D-172](../decisions.md#d-172-parallelworkers-defaults-to-one-minimum-worker)) |
| Max workers | **Required** | Finite explicit bound; never inferred from CPU capacity ([D-173](../decisions.md#d-173-parallelworkers-requires-an-explicit-maximum-worker-count)) |
| Sampling function | A fixed count | Absent a sampler, the count does not change |
| Sampling interval | 1 second | Used when a sampler is supplied; configurable ([D-174](../decisions.md#d-174-parallelworkers-defaults-sampling-to-one-second)) |
| Startup sampling | Immediate | May be deferred until after the first full interval |
| Scaling delta | 1 per sample | ([D-021](../decisions.md#d-021-worker-count-changes-by-one-per-sample-by-default)) |
| Clock | System clock | Injectable ([D-103](../decisions.md#d-103-the-clock-is-public-api)) |
| Synchronization provider | None | In-process by default; opt in for cross-instance membership/allocation ([SynchronizationProvider](./synchronization-provider.md)) |

## Advanced options

| Option | Shape | Effect |
| --- | --- | --- |
| Sampling function | `ctx -> number` | Dynamic worker count from live metrics |
| Sampling interval | duration | Evaluation frequency |
| Startup sampling | immediate or deferred | Whether the sampler runs at first start or after the first full interval |
| Max scaling delta | number | More than one change per interval |
| Min / max workers | numbers | Hard bounds around the sampled value |
| Event handlers | callbacks | `OnWorkerStart`, `OnWorkerStop`, `OnWorkerError`, `OnTaskComplete`, worker-count change |
| Clock / scheduler | injected | Deterministic sampling in tests |
| Synchronization provider | injected | Coordinated membership and worker allocation across instances ([SynchronizationProvider](./synchronization-provider.md#parallelworkers)) |
| Synchronization scope | caller-defined string | Namespaces one shared worker group |
| Adaptive capacity policy | injected, off by default | Adjusts the desired worker target within min/max/owner bounds ([AdaptiveCapacityPolicy](./adaptive-capacity-policy.md)) |

## Lifecycle, cancellation, and timeouts

- Shutdown drains every worker: stop reading, finish the current task, stop
  ([D-022](../decisions.md#d-022-workers-drain-gracefully-and-are-never-revived)).
- Cancel-pending shutdown cancels queued work, not the task a worker is currently
  running ([D-070](../decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending)).
- Disposal waits for every worker to reach `Dead` before releasing resources, and
  removes synchronized membership on the way out
  ([SynchronizationProvider](./synchronization-provider.md#shared-contract)).
- `ParallelWorkers` enforces no execution timeout of its own; timeouts belong to
  the owning utility's queue stages
  ([queue-and-admission.md](../subsystems/queue-and-admission.md#timeout-stages)).

## Composition

> Illustrative only.

```text
# What RateController does internally: workers pull from a bounded queue
# and the sampled count is clamped to N.

# What AsyncAccumulator does internally: each worker is a long-lived
# batching worker that accumulates items and invokes the batch function.
```

Both uses are documented in [rate-controller.md](./rate-controller.md) and
[async-accumulator.md](./async-accumulator.md). Direct use is equally valid for
recurring background work.

An optional [AdaptiveCapacityPolicy](./adaptive-capacity-policy.md) may
guide worker-target selection from saturation signals. It composes with, rather
than replaces, the user sampling function and normal clamp/scaling-delta rules.
When owned by `RateController`, it can never raise total in-flight work above
hard ceiling `N`. When used alongside `ThroughputController`, extra workers can
only consume work already released by the throughput credit scheduler.

## Invariants

- A dead worker is never revived ([INV-8](../architecture.md#invariants)).
- A retiring worker is never cancelled mid-task.
- The worker count never exceeds the owner's ceiling
  ([INV-4](../architecture.md#invariants)).
- Worker-count changes per sample never exceed the scaling delta.
- A failing work item never stops a worker's loop ([INV-12](../architecture.md#invariants)).

## Events and metrics

`OnWorkerStart`, `OnWorkerStop`, `OnWorkerError`, `OnTaskComplete`, worker
increment, worker-count change, and the periodic sample event. Snapshots expose
the current and desired worker counts. See
[observability.md](../subsystems/observability.md).

## Test coverage

Case IDs `PW-xxx` in [testing.md § ParallelWorkers](../testing.md#parallelworkers-pw).

## Open items

| Item | Status |
| --- | --- |
| Ownership of the first-item accumulation window when several batching workers are idle | Not decided ([async-accumulator.md](./async-accumulator.md#open-items)) |
