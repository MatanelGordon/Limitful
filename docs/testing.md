# Testing

**This document is the source of truth for test behavior.** When a design
document and a test disagree, this document and its matrix decide. When this
document changes a behavioral contract, every implemented binding affected by the
changed case IDs must be updated in the same change.

- [Implementation status](#implementation-status)
- [Two categories of test](#two-categories-of-test)
- [Case IDs and traceability](#case-ids-and-traceability)
- [Test doubles and override points](#test-doubles-and-override-points)
- [Deterministic time](#deterministic-time)
- [Deterministic concurrency](#deterministic-concurrency)
- [Coverage expectations](#coverage-expectations)
- [Test matrix](#test-matrix)
- [Cross-language parity process](#cross-language-parity-process)
- [Per-binding commands](#per-binding-commands)
- [Open items](#open-items)

## Implementation status

Development scaffolds exist for C#, TypeScript, Rust, Go, and Python. Their
package managers, builds, linters, formatters, and test runners are wired, but no
Limitful behavior has been implemented. Consequently, none of these scaffolds is
an implemented binding and the business-test matrix still has no language
coverage columns.

Consequences, and they are deliberate:

- **Do not add fake behavior or placeholder business tests** to make a scaffold
  look implemented. Tooling checks and packaging smoke tests prove only that the
  development environment works.
- The [test matrix](#test-matrix) below is the **portability contract**. It is
  written now so that the first binding has a definition of done, and so later
  bindings have a parity checklist rather than a reading exercise.
- The targets are C#, TypeScript, Rust, Go, and Python
  ([D-101](./decisions.md#d-101-api-surfaces-are-idiomatic-per-language)). Nothing
  here commits to an implementation order.
- When a binding implements behavior, its matrix rows move from `—` to pass/fail.
  Merely running the scaffold test command does not change matrix status.

**Full TDD is expected for every binding**: write the failing test for the case ID
first, implement, then refactor.

## Two categories of test

### Business tests

Verify core logic and API behavior that **must be identical across all
languages** ([INV-13](./architecture.md#invariants)). Driven from one shared spec
— the [test matrix](#test-matrix) in this document — which is the single source of
truth ([D-105](./decisions.md#d-105-business-tests-come-from-one-shared-markdown-spec)).

Generation and maintenance:

1. An LLM generates the appropriate **native** tests per language from the matrix.
2. Generated tests are then **committed and maintained as normal code**, not
   regenerated blindly. A hand-fixed test is the asset; the generator is scaffolding.
3. Every generated test carries its case ID
   ([case IDs and traceability](#case-ids-and-traceability)).

### Technical tests

Verify language-specific behavior that does not generalize. These are written per
language with variation, not uniformly, and they do **not** get shared case IDs.

Known technical-test areas:

| Area | Languages | Why it does not generalize |
| --- | --- | --- |
| Null / nil argument handling | C#, Go | `null` does not exist in all targets |
| Disposal patterns | C# `IDisposable` / `IAsyncDisposable`, Rust `Drop`, Python context managers, Go `defer` | Each language's resource idiom differs |
| Cancellation plumbing | C# `CancellationToken`, Go `context`, Rust cancellation, JS `AbortSignal` | The mechanism is idiomatic per language |
| The weighted admission lock | All, but especially C# | Peek → check → commit → remove must be synchronized per language's concurrency model ([weighted-async-accumulator.md § Thread safety](./utilities/weighted-async-accumulator.md#thread-safety)) |
| Achievable parallelism | Python, JavaScript | A single-threaded runtime cannot parallelize CPU work. **Semantics stay identical; only achievable concurrency differs** |
| Batch-outcome surface | C# especially | The ergonomic shape differs; the contract does not ([D-042](./decisions.md#d-042-outcome-correlation-is-positional-by-default-keyed-is-advanced)) |
| Concrete provider client integration | All | Backend adapters are provider-specific; controllers see only `SynchronizationProvider` ([D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract)) |

## Case IDs and traceability

Every business test case has a **stable ID**: a component prefix plus a number
([D-106](./decisions.md#d-106-stable-case-ids-trace-every-bindings-tests)).

| Prefix | Component |
| --- | --- |
| `RC` | [RateController](./utilities/rate-controller.md) |
| `TC` | [ThroughputController](./utilities/throughput-controller.md) |
| `JO` | [Shared controller contract](./subsystems/controller-contract.md) |
| `KCR` | [KeyedControllerRegistry](./utilities/keyed-controller-registry-draft.md) |
| `AC` | [AdaptiveCapacityPolicy](./utilities/adaptive-capacity-policy.md) |
| `SP` | [SynchronizationProvider](./utilities/synchronization-provider.md) |
| `PB` | [Probe](./utilities/probe.md) |
| `GRC` | [GroupedRateController](./utilities/grouped-rate-controller.md) |
| `PW` | [ParallelWorkers](./utilities/parallel-workers.md) |
| `AA` | [AsyncAccumulator](./utilities/async-accumulator.md) |
| `WAA` | [WeightedAsyncAccumulator](./utilities/weighted-async-accumulator.md) |
| `RD` | [RetryDecorator](./utilities/retry-decorator.md) |
| `QA` | [Queue and admission](./subsystems/queue-and-admission.md) |
| `RDS` | [Redis coordination](./subsystems/redis-synchronization.md) |
| `LC` | [Lifecycle and disposal](./architecture.md#lifecycle-and-disposal) |
| `OB` | [Observability](./subsystems/observability.md) |
| `ER` | [Shared error contract](./subsystems/controller-contract.md#error-contract) |

**Each language's test carries its case ID in a comment above the test.** When a
spec case changes, the ID locates every language's implementation of that case and
keeps all languages compliant with this document.

```text
// RC-003: a sampled worker count above N is clamped; in-flight never exceeds N
# AA-005: when idle, the first arriving item starts the full accumulation window
```

Rules:

- **IDs are stable and never reused.** A retired case keeps its number and is
  marked retired here; a changed behavior keeps its ID and gets a new description.
- **One ID may map to several tests per language** (for example, parameterized
  cases). All of them carry the ID.
- **A behavior with no ID is not a contract.** If you are implementing something
  that needs a test, add the case here first.

## Test doubles and override points

Every double is an ordinary **public override point**, not a test-only backdoor
([design-principles.md § Public override points](./design-principles.md#public-override-points)).
If a test needs a seam that does not exist for users, the seam is wrong.

| Double | Replaces | Makes deterministic |
| --- | --- | --- |
| **Virtual clock** | The clock / time source ([D-103](./decisions.md#d-103-the-clock-is-public-api)) | Timeouts, accumulation windows, backoff, heartbeats, sampling intervals |
| **Manual scheduler** | The delay / scheduler | *When* a pending delay completes, independent of wall time |
| **Seeded random source** | System randomness | Probabilistic retry prioritization ([D-016](./decisions.md#d-016-retry-scheduling-priority-is-configurable)) |
| **Scripted worker-count sampler** | The sampling function | Exact scale-up and scale-down sequences, delta-cap behavior |
| **Recording batch function** | The user batch function | Batch composition: how many calls, with which items, in which order |
| **Scripted batch function** | The user batch function | Default whole-batch mismatch failure, positional leniency, keyed missing results, and throwing batch functions ([D-181](./decisions.md#d-181-batch-correlation-mismatches-fail-the-whole-batch-by-default), [D-045](./decisions.md#d-045-a-throwing-batch-function-fails-every-input-in-that-batch)) |
| **Counting weight function** | The user weight function | That weight is computed exactly once, at insertion ([D-052](./decisions.md#d-052-item-weight-is-computed-once-at-insertion)) |
| **Scripted retry predicate** | `shouldRetry` | Which failures retry, and that cancellation ignores the predicate |
| **Gated job function** | The user function | Holding jobs in flight to observe ceiling enforcement |
| **Scripted synchronization provider** | `SynchronizationProvider` | Capability matching, atomic/idempotent claims, uncertain outcomes, health transitions, and recovery |
| **In-memory fake Redis adapter** | The Redis adapter ([D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)) | Redis sets, cardinality, staleness, scripts, slotting, **and induced outages** — no real Redis in the business suite |
| **Event recorder** | Event handlers | Which events fired, in what order, with what payloads |
| **Small configured limits** | Production-sized limits | Queue-full, batch-full, and over-weight paths, without volume |

### Overridden properties and options used by tests

These configuration values exist partly so tests can reach a path quickly. They
remain fully public ([D-102](./decisions.md#d-102-progressive-disclosure-sensible-defaults-advanced-opt-in)):

| Option | Test use |
| --- | --- |
| `concurrency`, group limits, global ceiling | `1` to serialize and make interleaving observable |
| `maxQueued` | `1` or `2` to reach full-queue behavior immediately |
| `maxBatchSize`, `maxBatchWeight` | Tiny values to exercise closing and carry-over |
| `accumulationInterval` | Driven by the virtual clock, never slept on |
| Timeout stages | Set individually to prove the stages are independent |
| `attempts` | `1` to prove retrying is off; `3` to prove the budget includes the first execution |
| Scaling delta, min/max workers | Prove clamping and one-change-per-sample |
| Sampling interval | Driven by the virtual clock |
| Overflow policy | Both modes, explicitly, in every queue-owning utility |
| Key prefix | Prove every key is namespaced |
| Heartbeat interval, staleness threshold | Prove disqualification without waiting |

## Deterministic time

**No test sleeps.** A `sleep`, a real timer, or a wall-clock assertion is a
defect, not a style preference.

1. **Inject the clock in every timing-dependent test.** This is required to keep
   timing tests fast and deterministic, and every language's API must support it
   ([D-103](./decisions.md#d-103-the-clock-is-public-api)).
2. **Advance time explicitly.** `clock.advance(interval)` then assert. Never
   "advance a bit more than the timeout to be safe".
3. **Assert at boundaries.** Just before the deadline: not fired. At or after:
   fired. A timeout test that only checks "eventually" proves nothing.
4. **Pair the clock with a manual scheduler** when the test needs to control the
   order in which two pending delays complete.
5. **Never assert on real elapsed duration.** Assert on observable
   state transitions and event order.
6. **Timeout-stage independence is a time test.** Each stage gets its own
   distinct value so an off-by-one-stage bug cannot pass
   ([queue-and-admission.md § Timeout stages](./subsystems/queue-and-admission.md#timeout-stages)).

## Deterministic concurrency

Concurrency tests must be reproducible. Thrashing threads and hoping is not a
test.

1. **Gate, do not race.** Use a latch or gate inside the job function to hold jobs
   in flight at a known point, assert the in-flight count, then release. This is
   how every ceiling assertion is made.
2. **Assert the maximum, not a sample.** Record the peak observed in-flight count
   across the run and assert `peak <= N` — a single mid-run reading can miss a
   violation.
3. **Prove the ceiling from the outside.** Count concurrent entries into the
   *user function*, not an internal counter, so the test cannot be fooled by
   accounting bugs.
4. **Make scale changes stepwise.** Drive the sampler with a script and advance
   the clock one interval at a time, asserting the count after each.
5. **Separate stress tests.** Randomized and high-volume soak tests are valuable
   but are tagged separately and excluded from the deterministic suite. They may
   never be the only coverage of a contract.
6. **Assert invariants continuously where possible** — a recorded in-flight peak,
   a "never executed after cancellation" flag, an exactly-once outcome counter —
   rather than only at the end.
7. **Interleaving hazards get targeted tests**, especially the weighted admission
   sequence: two batching workers contending must never claim the same item
   ([WAA-009](#weightedasyncaccumulator-waa)).

## Coverage expectations

- **Minimum 80% coverage per binding**, and the matrix is the floor, not the
  ceiling.
- Every binding must have unit tests (functions and components), integration tests
  (the utilities composed together), and end-to-end coverage of the critical
  flows: admission under load, batching under load, retry under a limiter, and
  coordinated shutdown.
- **Must be covered in every binding** — the non-negotiable list:
  1. Defaults, with nothing configured beyond the required value.
  2. Every advanced override path listed in
     [design-principles.md § Public override points](./design-principles.md#public-override-points).
  3. Cancellation at every stage: waiting for admission, queued, executing, during
     backoff.
  4. All three timeout stages, independently.
  5. Queue behavior: full, reject, wait, no drop-oldest, bounded depth.
  6. Retries: attempt counting, aggregated error, slot release, cancellation
     terminality.
  7. Grouped and global limits together, including the sum-exceeds-ceiling case.
  8. Composition: retry around a limiter, a limiter around a batch function.
  9. Lifecycle: both shutdown modes, and enqueue-after-shutdown.
  10. Observability: every documented event fires, and a throwing handler is
      isolated.

## Test matrix

**Status** values: `Ready` — decided and implementable now. `Blocked` — depends on
an open item; the row exists so the case is not forgotten, and must not be
implemented by guessing. Language columns are omitted entirely until a binding
exists ([implementation status](#implementation-status)).

### RateController (RC)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| RC-001 | With more than `N` jobs submitted at once, at most `N` execute concurrently | [D-001](./decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window) | Ready |
| RC-002 | 1,000 jobs submitted in the same instant all complete, and peak in-flight never exceeds `N` — no per-second cap exists | [D-001](./decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window) | Ready |
| RC-003 | A sampled worker count above `N` is clamped; peak in-flight never exceeds `N` | [D-002](./decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling) | Ready |
| RC-004 | A sampled worker count below `N` reduces parallelism but never raises the ceiling | [D-002](./decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling) | Ready |
| RC-005 | Completing a job releases its slot and admits the next queued job | [INV-4](./architecture.md#invariants) | Ready |
| RC-006 | A throwing job surfaces its failure to its own caller only | [D-005](./decisions.md#d-005-a-failing-task-is-isolated-to-itself) | Ready |
| RC-007 | A throwing job does not stop the queue, the workers, or sibling jobs | [INV-12](./architecture.md#invariants) | Ready |
| RC-008 | A throwing job raises the error event | [D-005](./decisions.md#d-005-a-failing-task-is-isolated-to-itself) | Ready |
| RC-009 | No configuration causes a failed job to be re-executed | [D-004](./decisions.md#d-004-ratecontroller-never-retries) | Ready |
| RC-010 | No minimum spacing is imposed between job starts | [D-001](./decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window) | Ready |
| RC-011 | A snapshot reports queue depth, in-flight count, and worker count consistently with observed state | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| RC-012 | Wrapping a function preserves its input and output contract | [design-principles.md](./design-principles.md#composability) | Ready |
| RC-013 | `concurrency = 1` serializes execution completely | [D-001](./decisions.md#d-001-ratecontroller-limits-by-concurrency-not-by-time-window) | Ready |
| RC-014 | Submitting after shutdown begins fails with cancellation | [INV-10](./architecture.md#invariants) | Ready |
| RC-015 | Invalid configuration fails at construction with an actionable message | [design-principles.md](./design-principles.md#error-handling) | Ready |

### ThroughputController (TC)

All time cases use a virtual monotonic clock and manual scheduler.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| TC-001 | A caller can select the shipped fixed-window strategy | [D-178](./decisions.md#d-178-throughputcontroller-ships-caller-selected-throughput-strategies) | Ready |
| TC-002 | A caller can select the shipped sliding-window strategy | [D-178](./decisions.md#d-178-throughputcontroller-ships-caller-selected-throughput-strategies) | Ready |
| TC-003 | A caller can select the shipped token-bucket strategy | [D-178](./decisions.md#d-178-throughputcontroller-ships-caller-selected-throughput-strategies) | Ready |
| TC-004 | Construction does not silently choose a throughput strategy for the caller | [D-178](./decisions.md#d-178-throughputcontroller-ships-caller-selected-throughput-strategies) | Ready |
| TC-005 | Omitted job cost is `1`; an explicit positive cost is evaluated once at submission | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready |
| TC-006 | Launch commit spends a job's cost exactly once; completion, failure, and post-launch cancellation do not refund it | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready |
| TC-007 | A non-positive, non-finite, or unsupported job cost fails with actionable validation | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready |
| TC-008 | A cost greater than the maximum quota balance fails at submission and never enters the queue | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready |
| TC-009 | With smooth pacing enabled, cost `C` advances eligibility by `C × period / rate` using conservative rounding | [throughput-controller.md](./utilities/throughput-controller.md#unresolved-design-questions) | **Blocked** — weighted pacing and rounding are not decided |
| TC-010 | A late scheduler wake-up never authorizes an early start or creates a catch-up burst | [throughput-controller.md](./utilities/throughput-controller.md#unresolved-design-questions) | **Blocked** — smooth pacing semantics are not decided |
| TC-011 | Configured minimum start spacing independently gates the next launch | [throughput-controller.md](./utilities/throughput-controller.md#optional-minimum-spacing-and-smooth-pacing) | Ready |
| TC-012 | Refill adds its amount lazily at each elapsed interval and never raises balance above capacity | [throughput-controller.md](./utilities/throughput-controller.md#quota-and-reservoir-behavior) | Ready |
| TC-013 | Reset replaces the balance at its boundary and discards unused prior balance | [throughput-controller.md](./utilities/throughput-controller.md#quota-and-reservoir-behavior) | Ready |
| TC-014 | Cancellation before launch commit wins without spending cost; a committed launch spends once and resolves once | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready — minimum atomic result; exact simultaneous race ordering remains blocked |
| TC-015 | Queue-wait expiry removes the job permanently and spends no credit | [INV-7](./architecture.md#invariants) | Ready |
| TC-016 | Priority changes selection order only and never bypasses pacing, spacing, quota, cancellation, or deadlines | [D-112](./decisions.md#d-112-priority-is-optional-banded-and-protected-by-aging) | Ready |
| TC-017 | Increasing the live rate creates no retroactive credit or replay of missed pacing ticks | [throughput-controller.md](./utilities/throughput-controller.md#unresolved-design-questions) | **Blocked** — pacing and live-update semantics are not decided |
| TC-018 | Reducing quota capacity clamps available balance, revokes no committed start, and evicts no queued work | [throughput-controller.md](./utilities/throughput-controller.md#unresolved-design-questions) | **Blocked** — live-update effects are not decided |
| TC-019 | One controller keeps at most one scheduler wake-up armed for the earliest eligibility while jobs queue | [D-166](./decisions.md#d-166-throughputcontroller-uses-one-bounded-event-driven-scheduler) | Ready |
| TC-020 | User functions, policies, and event handlers execute outside the scheduler lock and may re-enter read-only APIs | [D-166](./decisions.md#d-166-throughputcontroller-uses-one-bounded-event-driven-scheduler) | Ready |
| TC-021 | Drain rejects new work but continues honoring pacing and quota until every valid queued job settles | [D-166](./decisions.md#d-166-throughputcontroller-uses-one-bounded-event-driven-scheduler) | Ready |
| TC-022 | Cancel-pending announces cancellation for every queued job, spends no credit for them, and lets committed work finish | [D-166](./decisions.md#d-166-throughputcontroller-uses-one-bounded-event-driven-scheduler) | Ready |
| TC-023 | Without a composed concurrency controller, several slow jobs may remain in flight after their starts were validly admitted | [D-165](./decisions.md#d-165-throughputcontroller-spends-time-credits-atomically-at-launch) | Ready |
| TC-024 | Submitting after shutdown begins fails immediately and schedules no wake-up | [INV-10](./architecture.md#invariants) | Ready |
| TC-025 | A caller-supplied custom throughput strategy participates as a first-class strategy | [D-178](./decisions.md#d-178-throughputcontroller-ships-caller-selected-throughput-strategies) | **Blocked** — custom strategy support is open |

### GroupedRateController (GRC)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| GRC-001 | Each group's in-flight count stays at or under its own limit | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-002 | With the optional global ceiling enabled, global in-flight stays at or under it even when every group still has room | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-003 | With the global ceiling omitted, groups may concurrently reach the sum of their own limits | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-004 | An item is governed by the limit of the group whose predicate matched it | [D-061](./decisions.md#d-061-unmatched-items-route-to-a-default-group-or-throw) | Ready |
| GRC-005 | An unmatched item routes to the default group when one is configured | [D-061](./decisions.md#d-061-unmatched-items-route-to-a-default-group-or-throw) | Ready |
| GRC-006 | An unmatched item throws when no default group is configured | [D-061](./decisions.md#d-061-unmatched-items-route-to-a-default-group-or-throw) | Ready |
| GRC-007 | Under a contended global ceiling, the globally longest-waiting eligible job starts next regardless of group | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-008 | A group already at its own limit is skipped while other groups proceed | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-009 | A group never exceeds its limit even when it is the only group with work | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Ready |
| GRC-010 | Snapshots and events are attributable per group | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| GRC-011 | Shutdown applies to every group: queued items drain or cancel per mode | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | Ready |
| GRC-012 | Groups cannot be added or changed at runtime | [D-060](./decisions.md#d-060-groups-are-static) | Ready |
| GRC-013 | Retired — group-priority-over-fair-rotation arbitration was superseded by global FCFS | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Retired |
| GRC-014 | Retired — normalized group allocation was superseded by global FCFS job selection | [D-186](./decisions.md#d-186-grouped-global-ceiling-is-optional-with-global-fcfs-contention) | Retired |
| GRC-015 | A reserved share guarantees its group a minimum of the shared ceiling whenever it has demand | [D-132](./decisions.md#d-132-reserved-group-shares-are-accepted-in-direction-and-deferred-in-scope) | **Blocked** — deferred |
| GRC-016 | Unused reserved capacity is reclaimable by other groups and surrendered when demand returns | [D-132](./decisions.md#d-132-reserved-group-shares-are-accepted-in-direction-and-deferred-in-scope) | **Blocked** — deferred |
| GRC-017 | Reserved shares summing above the shared ceiling fail at construction | [D-132](./decisions.md#d-132-reserved-group-shares-are-accepted-in-direction-and-deferred-in-scope) | **Blocked** — deferred |

### ParallelWorkers (PW)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| PW-001 | After a sampling interval, the worker count moves toward the sampled value | [D-020](./decisions.md#d-020-worker-count-comes-from-a-user-sampling-function) | Ready |
| PW-002 | By default the count changes by at most one per sample | [D-021](./decisions.md#d-021-worker-count-changes-by-one-per-sample-by-default) | Ready |
| PW-003 | With a max delta of `k`, at most `k` changes occur per sample | [D-021](./decisions.md#d-021-worker-count-changes-by-one-per-sample-by-default) | Ready |
| PW-004 | A worker selected for removal finishes its current task before stopping | [D-022](./decisions.md#d-022-workers-drain-gracefully-and-are-never-revived) | Ready |
| PW-005 | A worker selected for removal takes no further item from the queue | [D-022](./decisions.md#d-022-workers-drain-gracefully-and-are-never-revived) | Ready |
| PW-006 | A dead worker is never revived; restored capacity comes from a fresh worker with a new identity | [INV-8](./architecture.md#invariants) | Ready |
| PW-007 | The sampling function receives live metrics in its context | [D-020](./decisions.md#d-020-worker-count-comes-from-a-user-sampling-function) | Ready |
| PW-008 | A sampled value outside min/max is clamped | [D-020](./decisions.md#d-020-worker-count-comes-from-a-user-sampling-function) | Ready |
| PW-009 | A sampled value above the owner's ceiling is clamped to the ceiling | [D-002](./decisions.md#d-002-n-is-the-hard-global-in-flight-ceiling) | Ready |
| PW-010 | A throwing task raises the worker-error event and the worker keeps looping | [INV-12](./architecture.md#invariants) | Ready |
| PW-011 | Worker start, stop, and task-complete events each fire exactly once per occurrence | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| PW-012 | The worker-count-change event reports the previous and new counts | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| PW-013 | Disposal returns only after every worker has reached the dead state | [architecture.md](./architecture.md#lifecycle-and-disposal) | Ready |
| PW-014 | No worker is started before first use | [design-principles.md](./design-principles.md#functional-conventions) | Ready |
| PW-015 | By default, a configured sampler runs immediately when the pool first starts, before the first recurring interval | [D-170](./decisions.md#d-170-parallelworkers-makes-startup-sampling-configurable) | Ready |
| PW-016 | Scheduled samples are skipped while a scale-up or graceful scale-down is still settling; the next regular tick after settlement may sample | [D-171](./decisions.md#d-171-parallelworkers-skips-sampling-during-worker-count-transitions) | Ready |
| PW-017 | Retired — worker-loop supervision is not a public Parallel Workers behavior | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-018 | Retired — worker replacement is not a Parallel Workers behavior | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-019 | Retired — worker capacity is not reduced in response to a work-item failure | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-020 | Retired — a work-item failure does not stop the owning controller | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-021 | Retired — no worker-failure event exists | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-022 | Retired — worker-loop loss is not a public behavior | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-023 | Retired — no replacement cycle exists | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-024 | Retired — supervised retirement does not exist | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-025 | Retired — no supervision callback exists | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-026 | Retired — no replacement backoff exists | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-027 | With deferred startup sampling, the first evaluation occurs only after one full sampling interval | [D-170](./decisions.md#d-170-parallelworkers-makes-startup-sampling-configurable) | Ready |
| PW-028 | Without an explicit minimum, the pool never scales below one worker | [D-172](./decisions.md#d-172-parallelworkers-defaults-to-one-minimum-worker) | Ready |
| PW-029 | Construction rejects a missing, non-positive, or non-finite maximum worker count | [D-173](./decisions.md#d-173-parallelworkers-requires-an-explicit-maximum-worker-count) | Ready |
| PW-030 | With a sampler and no explicit interval, sampling recurs at one-second intervals | [D-174](./decisions.md#d-174-parallelworkers-defaults-sampling-to-one-second) | Ready |
| PW-031 | Retired — automatic escalation is unnecessary because worker replacement does not exist | [D-176](./decisions.md#d-176-parallelworkers-does-not-model-worker-loop-failure) | Retired |
| PW-032 | An absent or invalid sample causes no scaling and preserves the current worker count | [D-183](./decisions.md#d-183-invalid-missing-failed-or-timed-out-samples-hold-worker-count) | Ready |
| PW-033 | A throwing sampler preserves the count and emits an error event | [D-183](./decisions.md#d-183-invalid-missing-failed-or-timed-out-samples-hold-worker-count) | Ready |
| PW-034 | A sampler that exceeds its timeout preserves the count; the default timeout equals the sampling interval | [D-183](./decisions.md#d-183-invalid-missing-failed-or-timed-out-samples-hold-worker-count) | Ready |
| PW-035 | A new sample never overlaps a sampler evaluation that is still running | [D-183](./decisions.md#d-183-invalid-missing-failed-or-timed-out-samples-hold-worker-count) | Ready |

### AsyncAccumulator (AA)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| AA-001 | A batch of `k` items produces exactly one batch-function call receiving all `k` inputs | [D-040](./decisions.md#d-040-asyncaccumulator-invokes-one-true-batch-function-per-batch) | Ready |
| AA-002 | Each caller receives only its own outcome, in positional correspondence with its input | [D-042](./decisions.md#d-042-outcome-correlation-is-positional-by-default-keyed-is-advanced) | Ready |
| AA-003 | A batch closes as soon as `maxBatchSize` is reached, without waiting for the window | [D-046](./decisions.md#d-046-batching-runs-on-parallelworkers-with-no-fixed-cadence) | Ready |
| AA-004 | A partial batch flushes immediately when the accumulation window elapses | [D-047](./decisions.md#d-047-the-accumulation-window-starts-when-the-first-item-arrives-after-idle) | Ready |
| AA-005 | While idle no countdown runs; the first arriving item starts the **full** window | [D-047](./decisions.md#d-047-the-accumulation-window-starts-when-the-first-item-arrives-after-idle) | Ready |
| AA-006 | While backlog remains, consecutive batches fire immediately with no cadence wait | [D-046](./decisions.md#d-046-batching-runs-on-parallelworkers-with-no-fixed-cadence) | Ready |
| AA-007 | The next batch's timing does not depend on the previous batch function's duration | [D-046](./decisions.md#d-046-batching-runs-on-parallelworkers-with-no-fixed-cadence) | Ready |
| AA-008 | In default positional mode, fewer outcomes than inputs fails the whole batch | [D-181](./decisions.md#d-181-batch-correlation-mismatches-fail-the-whole-batch-by-default) | Ready |
| AA-009 | In default positional mode, more outcomes than inputs fails the whole batch | [D-181](./decisions.md#d-181-batch-correlation-mismatches-fail-the-whole-batch-by-default) | Ready |
| AA-010 | A throwing batch function fails every input in that batch with the same batch-level failure | [D-045](./decisions.md#d-045-a-throwing-batch-function-fails-every-input-in-that-batch) | Ready |
| AA-011 | Keyed correlation returns each caller's outcome regardless of the returned order | [D-042](./decisions.md#d-042-outcome-correlation-is-positional-by-default-keyed-is-advanced) | Ready |
| AA-012 | An expired queue-wait timeout removes the item, which then appears in no later batch | [D-036](./decisions.md#d-036-a-queue-wait-timeout-removes-the-item-permanently) | Ready |
| AA-013 | A cancelled queued item appears in no batch, even while still physically queued | [D-037](./decisions.md#d-037-a-cancelled-item-never-runs) | Ready |
| AA-014 | A batch timeout completes every still-pending batch caller with timeout, does not stop the batch function, and holds the slot until it returns | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-015 | An expired pre-admission timeout fails the submission without the item entering the queue | [D-035](./decisions.md#d-035-timeout-scopes-are-distinct-per-lifecycle-stage) | Ready |
| AA-016 | Once execution begins, the queue-wait timeout no longer fires for that item | [D-035](./decisions.md#d-035-timeout-scopes-are-distinct-per-lifecycle-stage) | Ready |
| AA-017 | A batch never exceeds `maxBatchSize` | [D-040](./decisions.md#d-040-asyncaccumulator-invokes-one-true-batch-function-per-batch) | Ready |
| AA-018 | Drain flushes accumulated items, including a partial batch | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | Ready |
| AA-019 | Instance cancellation/cancel-dispose cancels queued items, signals running batches, and completes their callers with cancellation | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-020 | Every submitted item reaches exactly one terminal outcome | [INV-2](./architecture.md#invariants) | Ready |
| AA-021 | An optional injected `RateController` or `ThroughputController` governs batch operations without changing accumulation behavior | [D-180](./decisions.md#d-180-accumulators-accept-an-optional-controller) | Ready |
| AA-022 | A missing keyed result fails the whole batch by default | [D-181](./decisions.md#d-181-batch-correlation-mismatches-fail-the-whole-batch-by-default) | Ready |
| AA-023 | Positional lenient mode maps the returned prefix in order and fails the remaining inputs | [D-181](./decisions.md#d-181-batch-correlation-mismatches-fail-the-whole-batch-by-default) | Ready |
| AA-024 | A per-item timeout after batch start completes that caller immediately, does not cancel the batch, and discards the later value | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-025 | A per-item cancellation after batch start completes that caller immediately, does not cancel the batch, and discards the later value | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-026 | First-item window ownership when several batching workers are idle | [D-047](./decisions.md#d-047-the-accumulation-window-starts-when-the-first-item-arrives-after-idle) | **Blocked** — not decided |
| AA-027 | Manual flush closes the current batch immediately, without waiting out the window | [D-131](./decisions.md#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown) | Ready |
| AA-028 | Awaiting a manual flush awaits the batch outcomes, so it works as a barrier | [D-131](./decisions.md#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown) | Ready |
| AA-029 | Manual flush with more than `maxBatchSize` queued produces full batches plus one partial, never an oversized batch | [D-131](./decisions.md#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown) | Ready |
| AA-030 | Flushing an empty accumulator succeeds and invokes no batch function | [D-131](./decisions.md#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown) | Ready |
| AA-031 | Two concurrent flush requests coalesce to one batch boundary | [D-131](./decisions.md#d-131-batches-flush-on-size-weight-interval-manual-request-or-shutdown) | Ready |
| AA-032 | Manual flush does not bypass an injected or externally composed controller's admission | [D-180](./decisions.md#d-180-accumulators-accept-an-optional-controller) | Ready |
| AA-033 | After a manual flush the window does not restart until the next item arrives | [D-047](./decisions.md#d-047-the-accumulation-window-starts-when-the-first-item-arrives-after-idle) | Ready |
| AA-034 | Per-item timeout or cancellation while queued removes and fails the item before batching | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-035 | Per-item timeout or cancellation never cancels sibling items or their running batch | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-036 | Instance cancellation and cancel-dispose are the same terminal operation | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects) | Ready |
| AA-037 | Compensation runs once per affected batch after success with affected items and available results | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |
| AA-038 | Compensation runs once per affected batch after batch error with affected items and the error | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |
| AA-039 | Compensation runs after batch timeout and instance cancellation with every affected item and the applicable marker | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |
| AA-040 | Compensation failure emits an event, is not retried implicitly, and does not replace caller outcomes | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |
| AA-041 | Dispose waits for every pending compensation invocation | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |

### WeightedAsyncAccumulator (WAA)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| WAA-001 | The weight function is called exactly once per item, at submission | [D-052](./decisions.md#d-052-item-weight-is-computed-once-at-insertion) | Ready |
| WAA-002 | The weight function is never called during batch assembly | [D-052](./decisions.md#d-052-item-weight-is-computed-once-at-insertion) | Ready |
| WAA-003 | A batch's total weight never exceeds `maxBatchWeight` | [INV-9](./architecture.md#invariants) | Ready |
| WAA-004 | An item that would overshoot is carried to the next batch, never split and never dropped | [D-050](./decisions.md#d-050-a-batch-never-overshoots-max-weight) | Ready |
| WAA-005 | Strict mode rejects an item heavier than `maxBatchWeight` at submission | [D-051](./decisions.md#d-051-a-single-over-max-item-runs-alone-in-flexible-mode-is-blocked-in-strict-mode) | Ready |
| WAA-006 | Flexible mode runs an over-max item as a single-item batch | [D-051](./decisions.md#d-051-a-single-over-max-item-runs-alone-in-flexible-mode-is-blocked-in-strict-mode) | Ready |
| WAA-007 | A flexible-mode over-max item is never batched together with other items | [INV-9](./architecture.md#invariants) | Ready |
| WAA-008 | With a constant weight of 1 and `maxBatchWeight` equal to `maxBatchSize`, every `AA` size behavior is reproduced | [weighted-async-accumulator.md](./utilities/weighted-async-accumulator.md#test-coverage) | Ready |
| WAA-009 | Two contending batching workers never claim the same queued item, and committed batch weight always matches what was removed | [D-053](./decisions.md#d-053-the-weighted-admission-sequence-must-be-atomic) | Ready |
| WAA-010 | A carried-over item keeps its queue-wait deadline and cancellation behavior | [INV-7](./architecture.md#invariants) | Ready |
| WAA-011 | Snapshots report queued weight alongside queued count | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| WAA-012 | Drain flushes carried-over items as further batches | [INV-1](./architecture.md#invariants) | Ready |
| WAA-013 | The default over-max policy | [D-051](./decisions.md#d-051-a-single-over-max-item-runs-alone-in-flexible-mode-is-blocked-in-strict-mode) | **Blocked** — not decided |
| WAA-014 | Combining `maxBatchSize` with `maxBatchWeight`, and which bound takes precedence | — | **Blocked** — not decided |
| WAA-015 | Zero, negative, and throwing weight-function results | — | **Blocked** — not decided |
| WAA-016 | Every decided accumulator per-item, batch-timeout, instance-cancellation, controller-injection, and compensation case is inherited unchanged | [D-187](./decisions.md#d-187-accumulator-item-and-instance-signals-have-distinct-effects), [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |

### RetryDecorator (RD)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| RD-001 | `attempts = 3` produces at most three executions in total | [D-010](./decisions.md#d-010-the-retry-budget-is-named-attempts-and-includes-the-initial-execution) | Ready |
| RD-002 | `attempts = 1` executes once and never delays | [D-010](./decisions.md#d-010-the-retry-budget-is-named-attempts-and-includes-the-initial-execution) | Ready |
| RD-003 | Success on the first attempt incurs no delay and no attempt hook | [D-011](./decisions.md#d-011-retrydecorator-retries-every-ordinary-failure-by-default) | Ready |
| RD-004 | With no predicate supplied, every ordinary failure is retried until the budget is exhausted | [D-011](./decisions.md#d-011-retrydecorator-retries-every-ordinary-failure-by-default) | Ready |
| RD-005 | A fixed delay is configurable without defining any predicate | [D-011](./decisions.md#d-011-retrydecorator-retries-every-ordinary-failure-by-default) | Ready |
| RD-006 | Cancellation during an attempt is terminal; no further attempt runs | [INV-5](./architecture.md#invariants) | Ready |
| RD-007 | Cancellation during backoff is terminal; the remaining delay is abandoned | [D-012](./decisions.md#d-012-cancellation-is-terminal-during-retry) | Ready |
| RD-008 | A predicate that returns `true` for everything still does not cause cancellation to be retried | [D-012](./decisions.md#d-012-cancellation-is-terminal-during-retry) | Ready |
| RD-009 | A predicate returning `false` stops immediately, with the errors gathered so far | [D-017](./decisions.md#d-017-exhausted-retries-surface-an-aggregated-error) | Ready |
| RD-010 | An exhausted budget surfaces an aggregated error containing every attempt's error | [D-017](./decisions.md#d-017-exhausted-retries-surface-an-aggregated-error) | Ready |
| RD-011 | The backoff policy receives the item, the error, and current metrics | [D-013](./decisions.md#d-013-a-retrying-job-releases-its-concurrency-slot-during-backoff) | Ready |
| RD-012 | The per-attempt hook fires once per failed attempt with the attempt number and error | [D-017](./decisions.md#d-017-exhausted-retries-surface-an-aggregated-error) | Ready |
| RD-013 | Composed with a limiter, in-flight returns to zero during backoff — no slot is held | [INV-6](./architecture.md#invariants) | Ready |
| RD-014 | Each awaited attempt re-enters admission and acquires a new slot | [D-015](./decisions.md#d-015-awaited-retries-re-enter-normal-admission) | Ready |
| RD-015 | The deferred path returns to the caller immediately and reports the ultimate outcome through an event | [D-014](./decisions.md#d-014-two-retry-api-styles-awaited-and-deferred) | Ready |
| RD-016 | The deferred path reports ultimate failure through an event once the budget is exhausted | [D-014](./decisions.md#d-014-two-retry-api-styles-awaited-and-deferred) | Ready |
| RD-017 | Full retry prioritization places the retry ahead of queued work | [D-016](./decisions.md#d-016-retry-scheduling-priority-is-configurable) | **Blocked** — arbitration undefined |
| RD-018 | No prioritization places queued work ahead of the retry | [D-016](./decisions.md#d-016-retry-scheduling-priority-is-configurable) | **Blocked** — arbitration undefined |
| RD-019 | Probabilistic prioritization with a seeded random source produces the expected deterministic sequence | [D-016](./decisions.md#d-016-retry-scheduling-priority-is-configurable) | **Blocked** — arbitration undefined |
| RD-020 | None of the three priority modes starves normal queued work | [D-016](./decisions.md#d-016-retry-scheduling-priority-is-configurable) | **Blocked** — guarantees undefined |
| RD-021 | The default `attempts`, delay, backoff curve, and jitter | — | **Blocked** — not decided |
| RD-022 | A retry re-entering a **full** bounded queue | [D-015](./decisions.md#d-015-awaited-retries-re-enter-normal-admission) | **Blocked** — not decided |
| RD-023 | What counts as an "ordinary failure" per language | [D-011](./decisions.md#d-011-retrydecorator-retries-every-ordinary-failure-by-default) | **Blocked** — not decided |

### Queue and admission (QA)

Every queue-owning utility must pass this suite against its own surface.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| QA-001 | Enqueue succeeds while the queue is below capacity | [D-003](./decisions.md#d-003-queues-are-always-bounded) | Ready |
| QA-002 | In reject mode, a full queue fails insertion immediately and never waits for space | [D-030](./decisions.md#d-030-a-full-queue-rejects-immediately-by-default) | Ready |
| QA-003 | Reject is the default overflow mode with no configuration | [D-030](./decisions.md#d-030-a-full-queue-rejects-immediately-by-default) | Ready |
| QA-004 | In wait mode, a caller inside the configured waiting-caller capacity is admitted once space frees | [D-179](./decisions.md#d-179-wait-mode-has-a-configurable-bounded-waiting-room) | Ready |
| QA-005 | When the queue and bounded waiting room are full, the preferred outer-overflow default rejects the newcomer | [D-179](./decisions.md#d-179-wait-mode-has-a-configurable-bounded-waiting-room) | Ready |
| QA-006 | Admission order among waiters is not asserted, and no test may depend on FIFO | [D-033](./decisions.md#d-033-no-fifo-guarantee-for-admission-waiters) | Ready |
| QA-007 | Cancelling while awaiting insertion removes the request, which never enters the queue later | [D-034](./decisions.md#d-034-cancellation-while-awaiting-insertion-is-immediate-and-final) | Ready |
| QA-008 | An expired queue-wait timeout removes the item permanently; it never executes | [D-036](./decisions.md#d-036-a-queue-wait-timeout-removes-the-item-permanently) | Ready |
| QA-009 | A cancelled queued item never executes, even while still physically in the queue | [D-037](./decisions.md#d-037-a-cancelled-item-never-runs) | Ready |
| QA-010 | Queue depth never exceeds the configured maximum | [INV-3](./architecture.md#invariants) | Ready |
| QA-011 | No overflow path evicts an already-queued item — the oldest is never dropped | [INV-1](./architecture.md#invariants) | Ready |
| QA-012 | Every admitted item reaches exactly one terminal outcome | [INV-2](./architecture.md#invariants) | Ready |
| QA-013 | An expired pre-admission timeout fails the submission before entry | [D-035](./decisions.md#d-035-timeout-scopes-are-distinct-per-lifecycle-stage) | Ready |
| QA-014 | An expired execution timeout signals cancellation to the running function | [D-035](./decisions.md#d-035-timeout-scopes-are-distinct-per-lifecycle-stage) | Ready |
| QA-015 | The three timeout stages are independent: each fires only in its own window | [D-035](./decisions.md#d-035-timeout-scopes-are-distinct-per-lifecycle-stage) | Ready |
| QA-016 | Enqueue after shutdown begins fails with cancellation | [INV-10](./architecture.md#invariants) | Ready |
| QA-017 | When timeout or cancellation and the execution claim become ready together, the item still resolves exactly once | [queue-and-admission.md](./subsystems/queue-and-admission.md#cancellation) | Ready — minimum guarantee only; full rule **Blocked** |
| QA-018 | The precise atomic race rule between timeout/cancellation and claim or admission | [D-034](./decisions.md#d-034-cancellation-while-awaiting-insertion-is-immediate-and-final) | **Blocked** — not decided |
| QA-019 | Disposition of callers awaiting insertion when shutdown begins | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | **Blocked** — not decided |
| QA-020 | Explicit unbounded waiting admits beyond the configured waiting-caller capacity and reports that the memory guarantee is disabled | [D-179](./decisions.md#d-179-wait-mode-has-a-configurable-bounded-waiting-room) | Ready |
| QA-021 | Caller cancellation while executing wins the caller's eventual outcome, physical work completes, and the eventual work result is discarded | [D-182](./decisions.md#d-182-queued-cancellation-wins-the-caller-outcome-without-stopping-running-work) | Ready |

### Lifecycle and disposal (LC)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| LC-001 | Drain mode: queued jobs all complete, then disposal returns | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | Ready |
| LC-002 | Cancel-pending mode: queued-but-not-started jobs complete as cancelled | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | Ready |
| LC-003 | Cancel-pending mode: already-executing jobs are not cancelled and may finish normally | [D-070](./decisions.md#d-070-shutdown-is-either-drain-or-cancel-pending) | Ready |
| LC-004 | Both modes refuse new enqueues immediately with cancellation | [D-071](./decisions.md#d-071-enqueues-stop-immediately-once-shutdown-begins) | Ready |
| LC-005 | Disposal returns only after every worker has drained to dead | [D-022](./decisions.md#d-022-workers-drain-gracefully-and-are-never-revived) | Ready |
| LC-006 | No worker is cancelled mid-task by either shutdown mode | [D-022](./decisions.md#d-022-workers-drain-gracefully-and-are-never-revived) | Ready |
| LC-007 | With coordination enabled, disposal releases provider claims and removes membership before completing | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| LC-008 | Whether disposal is idempotent, and what a second disposal does | — | **Blocked** — not decided |
| LC-009 | Durable persistence across process exit | [D-072](./decisions.md#d-072-job-persistence-across-restarts-is-out-of-scope) | Not applicable — out of scope by decision |

### SynchronizationProvider (SP)

These cases use a scripted backend-neutral provider; they do not assert any
Redis command or storage layout.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| SP-001 | With no provider configured, a utility remains in-process and makes no synchronization call | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-002 | Coordination is enabled only for the utility receiving a provider; another utility in the same process remains local | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-003 | Missing a required capability fails configuration before work is accepted and names the utility and capability | [D-150](./decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration) | Ready |
| SP-004 | Capabilities are taken from the explicit declaration, never inferred from a provider or backend name | [D-150](./decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration) | Ready |
| SP-005 | A capability declared only for some conditions is rejected as unsupported for a strict requirement | [D-150](./decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration) | Ready |
| SP-006 | Repeating a membership or claim add with the same stable identity creates one authoritative entry | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-007 | Repeating release/removal for the same identity is harmless and cannot release another owner's state | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-008 | Retrying an uncertain reservation with the same idempotency ID returns the original grant or denial and spends once | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-009 | Two distinct scopes do not share claims, membership, limits, or configuration epochs | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-010 | Healthy, degraded/uncertain, and recovered transitions are observable without backend-specific fields | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-011 | A degraded local approximation is identified as degraded and is never reported as a hard global guarantee | [D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) | Ready |
| SP-012 | Recovery reconciles configuration epoch, leases, and stale membership before allowing capacity to increase | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-013 | `ThroughputController` rejects a provider lacking authoritative coordination time | [D-150](./decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration) | Ready |
| SP-014 | With an accurate synchronizer, `GroupedRateController` rejects one that can claim one limit atomically but cannot claim group and global limits together | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-015 | A stale configuration epoch may preserve a stricter allowance but never raises capacity from obsolete configuration | [synchronization-provider.md](./utilities/synchronization-provider.md#throughputcontroller) | Ready |
| SP-016 | Provider operations carry permission/shared state only; executable payloads and callbacks never cross the boundary | [D-161](./decisions.md#d-161-explicitly-out-of-scope) | Ready |
| SP-017 | Controller construction and operation use semantic provider operations and expose no backend client or raw command surface | [D-163](./decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract) | Ready |
| SP-018 | While the provider is degraded, every coordinated utility keeps admitting work on a finite local share (last known budget divided by last known instances); none fails closed | [D-199](./decisions.md#d-199-losing-the-synchronization-backend-never-stops-the-application) | Ready |
| SP-019 | A degraded `ThroughputController` continues at its divided share of the global rate, never at the full global rate | [D-199](./decisions.md#d-199-losing-the-synchronization-backend-never-stops-the-application) | Ready |
| SP-020 | Configuring coordination fails when the provider does not declare membership and health | [D-199](./decisions.md#d-199-losing-the-synchronization-backend-never-stops-the-application) | Ready |
| SP-021 | An instance that starts during an outage uses the provider's outage default limit, or the utility's normal configured limit when none is set, until coordination returns | [D-199](./decisions.md#d-199-losing-the-synchronization-backend-never-stops-the-application) | Ready |
| SP-022 | Every healthy instance refreshes its own heartbeat and removes peers whose heartbeat is stale, together with their claims and leases; no single instance is responsible | [D-200](./decisions.md#d-200-every-provider-runs-a-distributed-peer-healthcheck) | Ready |
| SP-023 | Two instances cleaning up the same dead peer at once leave one consistent result | [D-200](./decisions.md#d-200-every-provider-runs-a-distributed-peer-healthcheck) | Ready |
| SP-024 | With a loose synchronizer, a coordinated `RateController` makes no backend call per item; each instance enforces its local share of `N` | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-025 | With a loose synchronizer, when membership changes, the total in flight across instances exceeds `N` only until the next membership sample | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-026 | With a loose synchronizer, a coordinated `GroupedRateController` makes no backend call per item; each instance enforces its share of every group limit and of the global ceiling | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-027 | Every incoming item gets an admission check from its synchronizer before it starts; a denied item stays in the utility's bounded queue | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-028 | With no synchronization provider (`null`), a utility makes no synchronization call and no synchronizer admission check | [D-207](./decisions.md#d-207-no-synchronization-by-default) | Ready |
| SP-029 | With an accurate synchronizer and a healthy backend, the total in flight across instances never exceeds `N` | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-030 | An accurate synchronizer that loses its backend continues on the loose local share and returns to per-item claims after recovery and reconciliation | [D-204](./decisions.md#d-204-every-backend-has-an-accurate-and-a-loose-synchronizer) | Ready |
| SP-031 | Two synchronizers in one process use the one per-process healthcheck: one heartbeat, one membership entry, the same live count | [D-205](./decisions.md#d-205-the-healthcheck-is-a-separate-shareable-abstraction) | Ready |
| SP-032 | A backend call that takes longer than the timeout (default 500 ms) marks the backend down and the synchronizer continues on its local share | [D-208](./decisions.md#d-208-backend-calls-time-out-after-500-ms-and-a-timeout-means-the-backend-is-down) | Ready |
| SP-033 | The backend call timeout is configurable | [D-208](./decisions.md#d-208-backend-calls-time-out-after-500-ms-and-a-timeout-means-the-backend-is-down) | Ready |
| SP-034 | An item whose claim call timed out proceeds under the local share, and its claim is reconciled once after recovery | [D-208](./decisions.md#d-208-backend-calls-time-out-after-500-ms-and-a-timeout-means-the-backend-is-down) | Ready |

### Redis synchronization (RDS)

All cases run against the in-memory fake adapter with an injected clock.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| RDS-001 | Membership uses a sorted set with add/remove by ID, and the effective count is its cardinality | [D-082](./decisions.md#d-082-distributed-counting-is-set-based-never-increment-or-decrement) | Ready |
| RDS-002 | A repeated add of the same ID is idempotent — the count does not change | [INV-11](./architecture.md#invariants) | Ready |
| RDS-003 | A repeated remove of the same ID is idempotent | [INV-11](./architecture.md#invariants) | Ready |
| RDS-004 | No increment or decrement command is ever issued | [D-082](./decisions.md#d-082-distributed-counting-is-set-based-never-increment-or-decrement) | Ready |
| RDS-005 | An entity only removes its own ID, except via staleness-based disqualification | [D-086](./decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol) | Ready |
| RDS-006 | Two `LooseRedisSynchronization` instances divide `N`; their healthy local allowances do not sum above `N` | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Ready |
| RDS-007 | The heartbeat refreshes the instance's score in the membership sorted set on the configured interval | [D-086](./decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol) | Ready |
| RDS-008 | Any peer can remove members whose score is older than the staleness threshold; the count drops | [D-086](./decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol) | Ready |
| RDS-009 | Clean shutdown removes the process's own members | [D-086](./decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol) | Ready |
| RDS-010 | While the adapter is failing, a coordinated utility keeps using only its finite degraded local share | [D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) | Ready |
| RDS-011 | During that outage, the last sampled count is used to divide the allowance locally and degradation is observable | [D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) | Ready |
| RDS-012 | Frozen membership: a newly appearing worker adds no capacity while degraded | [D-084](./decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined) | Ready |
| RDS-013 | Frozen membership: a removal may reduce the allocation and never increases it again while degraded | [D-084](./decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined) | Ready |
| RDS-014 | On recovery, sampling and reconciliation complete before the allocation re-normalizes upward | [D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) | Ready |
| RDS-015 | Overshoot during an outage is bounded by membership drift, not unbounded | [D-164](./decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract) | Ready |
| RDS-016 | Every key carries the configured prefix | [D-087](./decisions.md#d-087-cluster-compliance-requires-deliberate-selective-slotting-and-a-user-prefix) | Ready |
| RDS-017 | Single-key operations impose no hash tag; multi-key operations use co-located keys | [D-087](./decisions.md#d-087-cluster-compliance-requires-deliberate-selective-slotting-and-a-user-prefix) | Ready |
| RDS-018 | Non-frozen membership behavior during an outage | [D-084](./decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined) | **Blocked** — not decided |
| RDS-019 | Division of `N` across processes, including integer remainders | — | **Blocked** — not decided |
| RDS-020 | Heartbeat scores use Redis server time, never the instance's local clock | [D-201](./decisions.md#d-201-redis-membership-and-heartbeats-live-in-one-sorted-set) | Ready |
| RDS-021 | Removing an evicted peer's claims and leases stored in other keys | [D-201](./decisions.md#d-201-redis-membership-and-heartbeats-live-in-one-sorted-set) | **Blocked** — not decided |
| RDS-022 | `RedisSynchronization` admits an item only through one atomic script that checks the claim count against the limit and adds the item's claim ID; no `INCR` | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Ready |
| RDS-023 | Releasing a claim removes its ID; repeating the release is harmless | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Ready |
| RDS-024 | Peer cleanup removes a dead instance's claims | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Ready for the behavior; key layout out of scope until implementation |
| RDS-025 | `LooseRedisSynchronization` issues no Redis command for an individual item; only healthcheck commands | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Ready |
| RDS-026 | The accurate grouped claim checks the group limit and the global ceiling together | [D-206](./decisions.md#d-206-redis-ships-redissynchronization-and-looseredissynchronization) | Deferred — key layout out of scope until implementation |

### Observability (OB)

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| OB-001 | Each documented event fires on its occurrence, with its documented payload | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| OB-002 | With no handler subscribed, behavior is unchanged and nothing throws | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| OB-003 | A throwing event handler does not break the emitting utility | [INV-12](./architecture.md#invariants) | Ready |
| OB-004 | Snapshot values are consistent with observed behavior | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| OB-005 | A held snapshot does not change as the utility continues working | [design-principles.md](./design-principles.md#immutability-where-it-belongs) | Ready |
| OB-006 | Event payloads do not expose mutable internal collections | [design-principles.md](./design-principles.md#immutability-where-it-belongs) | Ready |
| OB-007 | The sample event fires at its configured interval under a virtual clock | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| OB-008 | Every announced non-execution — timeout, cancellation, shutdown cancellation — is observable through events | [INV-2](./architecture.md#invariants) | Ready |
| OB-009 | The core package declares no observability dependency | [D-091](./decisions.md#d-091-otel-is-a-separate-opt-in-package-per-language) | Ready |
| OB-010 | Exact event payload shapes, delivery synchronicity, and ordering guarantees | — | **Blocked** — not decided |
| OB-011 | A compensation failure emits its dedicated event with the affected items and error | [D-188](./decisions.md#d-188-accumulator-compensation-runs-once-per-affected-batch) | Ready |

### Shared controller contract (JO)

Every `JO` case runs against **both** `RateController` and `ThroughputController`.
Divergence in a shared case is a contract bug, not a per-controller detail
([D-110](./decisions.md#d-110-a-shared-controller-contract-owns-submission-job-options-and-admission-queries)).

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| JO-001 | Function-only submission works with no `JobOptions` at all | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-002 | Every `JobOptions` field is independently optional | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-003 | A supplied `id` appears in events and snapshots and is not treated as a deduplication key | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-004 | An absent `id` is generated internally and is still correlatable | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-005 | `cost`, `priority`, and `deadline` are evaluated exactly once, at submission | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-006 | Zero, negative, non-finite, and out-of-range `cost` fail at submission | [D-111](./decisions.md#d-111-joboptions-is-one-shared-envelope-with-per-controller-cost-semantics) | Ready |
| JO-007 | A `cost` that can never be satisfiable fails at submission rather than queueing | [D-115](./decisions.md#d-115-deadline-aware-admission-rejects-at-submission-with-controller-bounded-accuracy) | Ready |
| JO-008 | `RateController` rejects a supplied `cost` with a clear error — it is never silently ignored | [D-116](./decisions.md#d-116-weighted-concurrency-cost-for-ratecontroller-is-deferred) | Ready |
| JO-009 | Priority changes selection order only; it never exceeds a ceiling, pace, or quota | [D-112](./decisions.md#d-112-priority-is-optional-banded-and-protected-by-aging) | Ready |
| JO-010 | Equal-priority work is served FIFO within its band | [D-112](./decisions.md#d-112-priority-is-optional-banded-and-protected-by-aging) | Ready |
| JO-011 | With priority enabled, a sustained high-priority stream does not starve lower-priority work under the default policy | [D-112](./decisions.md#d-112-priority-is-optional-banded-and-protected-by-aging) | Ready |
| JO-012 | Priority never makes cancellation non-terminal | [INV-5](./architecture.md#invariants) | Ready |
| JO-013 | `canStartNow` returns true when capacity is immediately available, false when saturated | [D-113](./decisions.md#d-113-admission-estimation-is-advisory-and-never-reserves-capacity) | Ready |
| JO-014 | `canStartNow` reserves nothing: two concurrent callers may both be told yes, and the ceiling still holds | [D-113](./decisions.md#d-113-admission-estimation-is-advisory-and-never-reserves-capacity) | Ready |
| JO-015 | Advisory queries never block and never mutate observable state | [D-113](./decisions.md#d-113-admission-estimation-is-advisory-and-never-reserves-capacity) | Ready |
| JO-016 | `ThroughputController.estimatedStartAt` returns a **computed** eligibility matching the pacing schedule under a virtual clock | [D-114](./decisions.md#d-114-estimatedstartat-is-best-effort-and-may-be-absent) | Ready |
| JO-017 | `RateController.estimatedStartAt` returns absence, or a value explicitly marked statistical — never a fabricated number | [D-114](./decisions.md#d-114-estimatedstartat-is-best-effort-and-may-be-absent) | Ready |
| JO-018 | A deadline that cannot be met is rejected at submission by `ThroughputController`, provably | [D-115](./decisions.md#d-115-deadline-aware-admission-rejects-at-submission-with-controller-bounded-accuracy) | Ready |
| JO-019 | `RateController` does not reject at submission on a statistical estimate; the job is accepted and its deadline expires in the queue | [D-115](./decisions.md#d-115-deadline-aware-admission-rejects-at-submission-with-controller-bounded-accuracy) | Ready |
| JO-020 | A deadline is re-checked before launch commit, and an expired job never starts | [D-036](./decisions.md#d-036-a-queue-wait-timeout-removes-the-item-permanently) | Ready |
| JO-021 | Every submission yields exactly one terminal outcome, including announced admission failures | [INV-2](./architecture.md#invariants) | Ready |
| JO-022 | Fire-and-forget uses the same scheduling path as an awaited submission | [D-110](./decisions.md#d-110-a-shared-controller-contract-owns-submission-job-options-and-admission-queries) | Ready |
| JO-023 | `cost` and `priority` numeric range, overflow, and rounding are identical in every binding | [INV-13](./architecture.md#invariants) | Ready |
| JO-024 | Number of priority bands and the default aging or weighted-fair algorithm | [D-112](./decisions.md#d-112-priority-is-optional-banded-and-protected-by-aging) | **Blocked** — not decided |
| JO-025 | Weighted concurrency cost on `RateController`, once a starvation rule exists | [D-116](./decisions.md#d-116-weighted-concurrency-cost-for-ratecontroller-is-deferred) | **Blocked** — deferred |
| JO-026 | Whether retry priority is expressed as `JobOptions.priority` | [D-141](./decisions.md#d-141-one-outcome-classification-vocabulary-is-shared-with-the-retry-predicate) | **Blocked** — not decided |
| JO-027 | A saturation snapshot exposes queue depth, in-flight count, waiting-caller count, and applicable cost/weight | [D-113](./decisions.md#d-113-admission-estimation-is-advisory-and-never-reserves-capacity) | Ready |
| JO-028 | Saturation snapshots are advisory and racy and never reserve admission | [D-113](./decisions.md#d-113-admission-estimation-is-advisory-and-never-reserves-capacity) | Ready |
| JO-029 | With deduplication enabled, a duplicate queued job is rejected as `AlreadyQueued` and never shares the original result | [D-184](./decisions.md#d-184-optional-queued-job-deduplication-rejects-duplicates) | Ready |
| JO-030 | Deduplication uses the caller's hash/key function and remains separate from the correlation ID | [D-184](./decisions.md#d-184-optional-queued-job-deduplication-rejects-duplicates) | Ready |

### Shared error contract (ER)

Every binding uses idiomatic syntax while preserving these semantic categories
and default result behavior.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| ER-001 | Expected operation outcomes use a `Result` or value-or-error form by default rather than throwing | [D-185](./decisions.md#d-185-expected-outcomes-use-semantic-library-errors-and-result-values) | Ready |
| ER-002 | Throwing, raising, or unwrapping a failed result requires explicit caller opt-in | [D-185](./decisions.md#d-185-expected-outcomes-use-semantic-library-errors-and-result-values) | Ready |
| ER-003 | Queue full, waiting-room full, timeout, cancellation, `AlreadyQueued`, invalid cost/weight, contract violation, and task failure are distinguishable semantic library errors | [D-185](./decisions.md#d-185-expected-outcomes-use-semantic-library-errors-and-result-values) | Ready |
| ER-004 | A user-function failure is wrapped as a known task-failed library error | [D-185](./decisions.md#d-185-expected-outcomes-use-semantic-library-errors-and-result-values) | Ready |
| ER-005 | The task-failed error exposes the original user failure as its cause | [D-185](./decisions.md#d-185-expected-outcomes-use-semantic-library-errors-and-result-values) | Ready |
| ER-006 | Equivalent failures map to the same semantic category in all five languages | [INV-13](./architecture.md#invariants) | Ready |

### KeyedControllerRegistry (KCR)

Every `QA` case must also pass through a registry-wrapped controller unchanged —
that is the proof the registry adds no admission semantics
([D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key)).

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| KCR-001 | A first submission for a new key creates exactly one controller and runs the work | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-002 | Subsequent submissions for the same key reuse that controller | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-003 | Concurrent first submissions for the same key create exactly one controller, and all of them use it | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-004 | Different keys are isolated: saturating one key does not delay another | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-005 | The key selector runs once per submission and its result routes the work | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-006 | A throwing key selector fails that submission at submission time, before any queue | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-007 | Construction fails when `idleTimeToLive` or `maxActiveKeys` is absent | [D-121](./decisions.md#d-121-idle-ttl-and-maximum-active-keys-are-mandatory) | Ready |
| KCR-008 | There is no "never expire" or infinite-key configuration | [D-121](./decisions.md#d-121-idle-ttl-and-maximum-active-keys-are-mandatory) | Ready |
| KCR-009 | An idle key is evicted after `idleTimeToLive` under a virtual clock | [D-122](./decisions.md#d-122-eviction-never-discards-live-work) | Ready |
| KCR-010 | A key with queued work is **never** evicted, however long it has been idle by wall time | [D-122](./decisions.md#d-122-eviction-never-discards-live-work) | Ready |
| KCR-011 | A key with work in flight is never evicted | [D-122](./decisions.md#d-122-eviction-never-discards-live-work) | Ready |
| KCR-012 | A submission arriving for an evictable key revives it rather than racing its eviction | [D-122](./decisions.md#d-122-eviction-never-discards-live-work) | Ready |
| KCR-013 | Eviction disposes the controller; it is not abandoned to the garbage collector | [D-122](./decisions.md#d-122-eviction-never-discards-live-work) | Ready |
| KCR-014 | At `maxActiveKeys`, a new key's submission is **rejected**, and no live key is evicted to make room | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | Ready |
| KCR-015 | The at-capacity rejection reason is distinguishable from queue overflow | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | Ready |
| KCR-016 | Idle keys are swept before a capacity rejection, so an evictable key yields room | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | Ready |
| KCR-017 | Active-key count never exceeds `maxActiveKeys` under concurrent new-key pressure | [D-121](./decisions.md#d-121-idle-ttl-and-maximum-active-keys-are-mandatory) | Ready |
| KCR-018 | With a `globalCeiling`, aggregate in-flight across all keys never exceeds it | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | Ready |
| KCR-019 | Without a `globalCeiling`, the snapshot reports worst-case aggregate concurrency | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | Ready |
| KCR-020 | Snapshots report active keys, high-water mark, eviction count, and refusal count | [D-124](./decisions.md#d-124-registry-disposal-propagates-and-evictions-are-observable) | Ready |
| KCR-021 | Key created, evicted, and refused events each fire once per occurrence | [D-124](./decisions.md#d-124-registry-disposal-propagates-and-evictions-are-observable) | Ready |
| KCR-022 | Disposal stops accepting new keys and new submissions immediately | [INV-10](./architecture.md#invariants) | Ready |
| KCR-023 | Disposal disposes every live controller under the chosen mode and returns only when all are disposed | [D-124](./decisions.md#d-124-registry-disposal-propagates-and-evictions-are-observable) | Ready |
| KCR-024 | No background work occurs before the first submission | [design-principles.md](./design-principles.md#functional-conventions) | Ready |
| KCR-025 | A registry over `ThroughputController` behaves identically for all key-lifecycle cases | [D-110](./decisions.md#d-110-a-shared-controller-contract-owns-submission-job-options-and-admission-queries) | Ready |
| KCR-026 | The full `QA` suite passes unchanged through a registry-wrapped controller | [D-120](./decisions.md#d-120-keyedcontrollerregistry-creates-one-controller-per-dynamic-key) | Ready |
| KCR-027 | Whether `globalCeiling` is mandatory | [D-123](./decisions.md#d-123-at-capacity-refusal-is-distinct-from-queue-overflow) | **Blocked** — not decided |
| KCR-028 | Idle-TTL measurement origin: last submission versus became-empty | — | **Blocked** — not decided |
| KCR-029 | Eviction selection among several evictable keys | — | **Blocked** — not decided |

### AdaptiveCapacityPolicy (AC)

Signals are supplied directly rather than measured, under an injected clock.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| AC-001 | A controller built without naming a policy performs no adaptation at all | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-002 | `Throttled` outcomes reduce effective capacity | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-003 | `Overloaded` outcomes reduce effective capacity | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-004 | **`CallerError` outcomes have no capacity effect**, however many arrive | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-005 | `TransientFailure` is neutral by default | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-006 | `Ignore` outcomes are excluded from every adaptive input | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-007 | With no classifier supplied, raw failures alone never reduce capacity | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-008 | Cancellation is never treated as a capacity signal | [INV-5](./architecture.md#invariants) | Ready |
| AC-009 | Classification never alters the caller's own returned outcome | [D-140](./decisions.md#d-140-callers-classify-outcomes-the-library-never-infers-capacity-pressure-from-generic-failures) | Ready |
| AC-010 | A throwing classifier or policy falls back to the nominal limit and never retains an overclock | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-011 | A proposed capacity above the configured envelope is clamped | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-012 | Adaptation can never raise `RateController` in-flight work above `N` | [INV-4](./architecture.md#invariants) | Ready |
| AC-013 | Overclock requires explicit enablement; an absolute maximum above nominal alone does not enable it | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-014 | Enter and exit thresholds are distinct, and a single busy sample does not trigger an overclock | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-015 | Overclock expires under virtual time even if no new signal arrives | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-016 | A stale or invalid signal returns capacity to nominal immediately | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-017 | Unused adaptive headroom never accumulates as a later burst | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | Ready |
| AC-018 | Every accepted and rejected adaptation is observable with its bounded reason code | [D-090](./decisions.md#d-090-observability-is-event-driven-and-exposes-raw-data) | Ready |
| AC-019 | Whether `Throttled` reduces capacity more aggressively than `Overloaded` | — | **Blocked** — not decided |
| AC-020 | Default sample interval, stale threshold, dead band, dwell, hold, overclock duration, and cooldown | — | **Blocked** — not decided |
| AC-021 | Congestion-preset behavior | [D-142](./decisions.md#d-142-adaptive-presets-are-opt-in-and-the-congestion-preset-comes-later) | **Blocked** — deferred |
| AC-022 | Policy evaluation receives one immutable normalized context and returns a bounded reason code without mutating controller state | [D-167](./decisions.md#d-167-adaptivecapacitypolicy-proposes-controllers-validate-and-clamp) | Ready |
| AC-023 | Policy evaluation runs outside scheduling locks; a policy may re-enter read-only controller APIs without deadlock | [D-167](./decisions.md#d-167-adaptivecapacitypolicy-proposes-controllers-validate-and-clamp) | Ready |
| AC-024 | Submitting jobs does not evaluate the policy per job; evaluation occurs only at its configured interval or a pushed sample | [D-167](./decisions.md#d-167-adaptivecapacitypolicy-proposes-controllers-validate-and-clamp) | Ready |
| AC-025 | Shutdown ends an active overclock immediately and no later policy result can raise capacity | [D-167](./decisions.md#d-167-adaptivecapacitypolicy-proposes-controllers-validate-and-clamp) | Ready |
| AC-026 | Adaptation changes only the controller's documented effective bound; it never mints quota or bypasses another hard gate | [D-167](./decisions.md#d-167-adaptivecapacitypolicy-proposes-controllers-validate-and-clamp) | Ready |

### Probe (PB)

All timing and timeout cases use a virtual monotonic clock and manual scheduler.

| ID | Case | Source | Status |
| --- | --- | --- | --- |
| PB-001 | Before the first successful refresh, `current()` returns absence and the snapshot reports no value | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-002 | Construction starts the first refresh immediately without waiting one interval | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-003 | A successful refresh atomically publishes the value, success/attempt times, clears the latest failure, and increments generation once | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-004 | A failed refresh updates attempt/failure metadata but preserves the previous value, success time, and generation | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-005 | `current()` returns the last-known-good value even when the latest attempt failed or the value is stale | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-006 | `isFresh` changes exactly at the configured freshness boundary under virtual time | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-007 | A slow measurement never overlaps another invocation for the same probe | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-008 | One or more intervals becoming due during an active measurement coalesce into one subsequent refresh, not one call per missed tick | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-009 | By default a refresh receives cooperative timeout/cancellation when one interval elapses | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-010 | Snapshot readers observe either the complete old state or complete new state, never a partial publication | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-011 | The measurement function runs outside probe synchronization and may read the current snapshot without deadlock | [D-169](./decisions.md#d-169-probe-refreshes-serially-and-coalesces-missed-intervals) | Ready |
| PB-012 | Default `historyCapacity = 1` retains only the latest successful value | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-013 | Configured history capacity `N` retains at most the latest `N` successful values under repeated refreshes | [D-168](./decisions.md#d-168-probe-retains-the-latest-successful-value-with-freshness-metadata) | Ready |
| PB-014 | A non-positive refresh interval or history capacity fails construction with an actionable message | [design-principles.md](./design-principles.md#error-handling) | Ready |
| PB-015 | A ProbeFactory shares one due-time scheduler across its created probes while each probe retains independent snapshots and freshness | [D-177](./decisions.md#d-177-probefactory-shares-due-time-scheduling-across-probes) | Ready |
| PB-016 | Different, jittered, and dynamically changed intervals schedule by earliest next due time rather than an LCM/GCD timing grid | [D-177](./decisions.md#d-177-probefactory-shares-due-time-scheduling-across-probes) | Ready |
| PB-017 | With the default unlimited factory cap, every due probe may begin immediately, while no individual probe overlaps its own measurement | [D-177](./decisions.md#d-177-probefactory-shares-due-time-scheduling-across-probes) | Ready |
| PB-018 | With a finite factory cap, excess due probes wait for capacity and coalesce missed intervals into one later refresh | [D-177](./decisions.md#d-177-probefactory-shares-due-time-scheduling-across-probes) | Ready |

## Cross-language parity process

1. **A behavioral change starts here.** Edit the matrix row, or add one, and
   record the decision in [decisions.md](./decisions.md).
2. **Find every implementation of the changed case IDs** by grepping for the ID
   across bindings. That is the entire point of the ID convention.
3. **Update every affected binding in the same change.** A binding left behind is
   a parity break, not a follow-up task.
4. **If a binding cannot satisfy the change**, that is a specification problem.
   Either the contract is wrong, or the case belongs in
   [technical tests](#technical-tests) with an explicit per-language variation
   recorded here. Silent divergence is never acceptable
   ([INV-13](./architecture.md#invariants)).
5. **A `Blocked` row is never implemented by guessing.** Decide it in
   [decisions.md](./decisions.md) first, then move the row to `Ready`.
6. **Retiring a case** keeps its ID, marks it retired here, and removes it from
   every binding in the same change.

## Per-binding commands

These commands validate the development scaffolds. They do not claim behavioral
coverage, integration coverage, or the 80% target described above.

| Binding | Runner | Command | Status |
| --- | --- | --- | --- |
| C# | xUnit v3 (`xunit.v3` 4.0.2) | `make test-csharp` | Scaffold only; no behavior tests |
| TypeScript | Vitest 5.0.3 | `make test-typescript` | Scaffold only; no behavior tests |
| Rust | Built-in Rust test harness | `make test-rust` | Scaffold only; no behavior tests |
| Go | Built-in `go test` harness | `make test-go` | Scaffold only; no behavior tests |
| Python | pytest 9.1.1 | `make test-python` | Packaging/import smoke test only |

Run all five with `make test`, or the full formatting, linting, build, and test
matrix with `make check`.

## Open items

| Item | Status |
| --- | --- |
| Which binding lands first, and therefore which becomes the reference implementation | Not decided |
| Coverage tool choices for implemented bindings | Not decided; select them when behavioral implementation begins |
| Whether the matrix is additionally machine-readable, so parity can be checked in CI rather than by grep | Not decided. Surfaced during consolidation |
| Whether stress and soak suites run in CI or on demand | Not decided. Surfaced during consolidation |
