# Design Principles

Limitee has one organizing rule: **the easy thing must be easy, and the hard
thing must be possible without forking the library.** Everything below is a
consequence of that rule.

- [Progressive disclosure](#progressive-disclosure)
- [Policy versus mechanism](#policy-versus-mechanism)
- [Public override points](#public-override-points)
- [Functional conventions](#functional-conventions)
- [Immutability where it belongs](#immutability-where-it-belongs)
- [Composability](#composability)
- [Error handling](#error-handling)
- [Naming](#naming)
- [Anti-patterns](#anti-patterns)

## Progressive disclosure

A first-time user should get correct, safe behavior from the smallest possible
call. Advanced behavior exists behind explicit options, properties, and injected
functions — never as a precondition
([D-102](./decisions.md#d-102-progressive-disclosure-sensible-defaults-advanced-opt-in)).

> Illustrative pseudocode throughout this document. No public API is committed yet.

```text
# Level 0 — nothing but the limit
limiter = rateController({ concurrency: 10 })

# Level 1 — a named option
limiter = rateController({ concurrency: 10, maxQueued: 1000 })

# Level 2 — injected policy
limiter = rateController({
  concurrency: 10,
  maxQueued: 1000,
  onOverflow: Overflow.AwaitInsertion,
  workerCount: ctx => ctx.queueDepth > 500 ? 10 : 4,
  clock: myTestClock,
})
```

Rules that keep this honest:

1. **Every value and behavior has a default.** If a knob has no sensible default,
   that is a design problem with the knob, not a reason to require it.
2. **Defaults must be safe, understandable, and ergonomic** — in that order. Safe
   means it cannot silently lose work or silently exceed a limit. Understandable
   means a reader can predict it without reading the source.
3. **Defaults are documented as values, not as prose.** Each utility document
   carries a defaults table; an undecided default is written as `Undecided` and
   listed as an open item rather than quietly invented.
4. **No knob is required to reach correct behavior.** A user who sets only the
   limit gets a correct limiter, not a half-configured one.
5. **Advanced features do not change simple behavior.** Adding a retry predicate
   must not alter the no-predicate default path.
6. **Testing hooks are public API, not test-only backdoors.** The clock exists so
   tests can control time, and advanced users may swap it
   ([D-103](./decisions.md#d-103-the-clock-is-public-api)).

### What "simple" costs

Progressive disclosure is not free, and the price is paid deliberately:
reject-on-full is the default even though waiting is friendlier, because waiting
has unbounded memory consequences the library refuses to hide
([D-030](./decisions.md#d-030-a-full-queue-rejects-immediately-by-default)).
A default that is friendly but unsafe is the wrong default.

## Policy versus mechanism

Limitee ships **mechanism**. Every decision that depends on the caller's domain
is **policy**, and policy is injected.

| Mechanism — the library owns it | Policy — the caller owns it |
| --- | --- |
| Counting in-flight work and enforcing the ceiling | How many workers to run right now |
| Holding a bounded queue and honoring its capacity | What to do when it is full |
| Running attempts and waiting between them | Whether a given error deserves another attempt, and how long to wait |
| Closing a batch when it is full or its window elapsed | How heavy an item is |
| Routing an item to a group | Which group an item belongs to |
| Counting membership across processes | How to talk to Redis |
| Advancing time | What time it is, under test |

Two consequences:

- **Mechanism code contains no domain branching.** There is no
  `if (isHttpTimeout)` anywhere in the library; that is what a retry predicate is
  for.
- **Policy is a function, not a configuration enum**, whenever the answer could
  depend on runtime context. A worker count is a function of live metrics; a
  backoff delay is a function of the item, the error, and current metrics. Enums
  are reserved for genuinely closed sets, such as overflow mode.

## Public override points

These are the sanctioned seams. They exist for advanced callers *and* for
deterministic tests, and the test strategy depends on them
([testing.md § Test doubles](./testing.md#test-doubles-and-override-points)).

| Seam | Shape | Used for | Default |
| --- | --- | --- | --- |
| Clock / time source | injected object | virtual time in tests, custom time sources | system clock |
| Delay / scheduler | injected object | deterministic backoff and accumulation windows | clock-backed real delay |
| Random source | injected function | seeding probabilistic retry prioritization | system randomness |
| Worker-count sampler | `ctx -> number` | dynamic scaling | a fixed count derived from the configured limit |
| Sampling interval | duration | how often the sampler runs | `Undecided` — see [parallel-workers.md](./utilities/parallel-workers.md#defaults) |
| Retry predicate | `(error, ctx) -> bool` | which failures deserve another attempt | retry every ordinary failure; cancellation is never retried |
| Backoff policy | `(ctx) -> duration` | exponential, jittered, or domain-aware waiting | `Undecided` — see [retry-decorator.md](./utilities/retry-decorator.md#defaults) |
| Attempt hooks | callbacks | logging, metrics, custom handling per attempt | none |
| Overflow policy | enum | reject vs await insertion | reject |
| Group predicates | `item -> bool` per group | routing into static groups | none; groups are explicit |
| Group priority | advanced option | priority over fair rotation | fair rotation |
| Weight function | `item -> weight` | weight-budgeted batching | required for the weighted accumulator only |
| Outcome correlation | positional or keyed | reordered or partial batch results | positional |
| Redis adapter | injected interface | any Redis client, or a fake in tests | none; absent means in-memory mode |
| Queue capacity and timeout stages | values | backpressure shaping | see each utility's defaults table |

**Rule for adding a seam.** A new override point is justified only when the
library cannot pick a defensible default *and* the answer depends on the caller's
domain. Otherwise pick the default. Seams are API surface forever.

## Functional conventions

Limitee uses objects where a lifetime must be owned and disposed, and functions
everywhere else
([D-104](./decisions.md#d-104-prefer-functions-and-events-over-object-orientation)).

1. **Pure functions for decisions.** Predicates, samplers, weight functions, and
   backoff policies take context and return a value. They must not mutate library
   state; the library may call them at any time, possibly concurrently.
2. **Explicit state transitions.** Worker and job lifecycles are modeled as named
   states with enumerated transitions
   ([architecture.md § Lifecycle](./architecture.md#lifecycle-and-disposal),
   [parallel-workers.md](./utilities/parallel-workers.md)). No state is implied by
   a boolean pair, and no state is reachable by accident. A dead worker cannot
   become alive ([INV-8](./architecture.md#invariants)) because no transition
   exists.
3. **Small composable units.** Prefer many small files with high cohesion over
   few large ones: admission, slot accounting, worker loop, batching loop, and
   timeout bookkeeping are separate units that can be reasoned about and tested
   alone.
4. **Minimal hidden behavior.** No ambient singletons, no implicit global
   registry, no background thread before first use, no retry a caller did not
   ask for, no hidden logging. If something happens, either the caller asked for
   it or an event announces it.
5. **Events over inheritance.** Extension happens by subscribing to events and
   injecting functions, not by subclassing. No binding should require the user to
   derive from a library base class.
6. **Functional core, imperative shell.** Decision logic — should this be
   admitted, does this item fit the batch, how many workers should exist — is
   written as pure functions over snapshots. Only a thin shell performs the
   synchronized mutation.
7. **Idiomatic result handling.** Where a language has a natural
   result-or-error type, expected failures use it rather than exceptions;
   C# and Rust bindings lean on records, unions, and exhaustive matching.

## Immutability where it belongs

Immutability is a tool, not a religion: a concurrency limiter is a mutable
counter by nature. The boundary is sharp.

**Immutable:**

- Configuration objects, once constructed. Reconfiguration produces a new
  instance or goes through an explicit documented mutator — never a silently
  mutated field.
- Metrics and state snapshots. A snapshot is a value with no live link to the
  source, so a caller can hold one without tearing.
- Event payloads. Handlers receive values and cannot mutate library state by
  editing what they were handed.
- Queued-item wrappers. An item plus its precomputed weight, deadlines, and
  identity is built once at insertion and never edited in place
  ([D-052](./decisions.md#d-052-item-weight-is-computed-once-at-insertion)).
- Anything handed to user code. Never pass out a live internal collection.

**Mutable, and deliberately so:**

- Slot accounting, queue contents, and worker registries. These are the
  mechanism. They are small, local, and explicitly synchronized.
- The synchronized admission sequence. Peek → check budget → commit → remove must
  be atomic; the weighted accumulator's version of this is a genuine concurrency
  hazard and is called out as such
  ([weighted-async-accumulator.md § Thread safety](./utilities/weighted-async-accumulator.md#thread-safety)).

The rule: **immutable at the boundary, synchronized at the core.** Anything a
user can observe or hold is a value; anything the library mutates is behind a
lock and never escapes.

## Composability

- **Utilities compose by wrapping functions**, not by registering with each other
  ([architecture.md § Composition](./architecture.md#composition-guidance)).
- **No utility secretly uses another on the caller's behalf.**
  `AsyncAccumulator` will not rate-limit for you
  ([D-041](./decisions.md#d-041-asyncaccumulator-does-not-integrate-with-ratecontroller));
  `RateController` will not retry for you
  ([D-004](./decisions.md#d-004-ratecontroller-never-retries)).
- **Composition order is the caller's decision and is documented**, including
  which order is usually wrong and why.
- **Decorators are transparent.** A wrapped function keeps its input and output
  contract; wrapping changes timing and failure modes, never the signature's
  meaning.
- **Each utility is independently useful.** `ParallelWorkers` without
  `RateController`, `RetryDecorator` without a queue, and the accumulators
  without either are all first-class uses.

## Error handling

- **Never swallow.** Every failure reaches the caller, an event, or both.
- **Isolate.** One task's failure never disturbs the queue, the workers, or
  sibling tasks ([INV-12](./architecture.md#invariants)).
- **Aggregate across attempts.** When a retried call finally fails, surface the
  combination of every error encountered, not only the last one
  ([D-017](./decisions.md#d-017-exhausted-retries-surface-an-aggregated-error)).
- **Distinguish contract errors from task failures.** A user batch function that
  returns more outcomes than inputs has violated a contract; that is surfaced as
  a contract error, not as a per-item failure
  ([D-044](./decisions.md#d-044-surplus-positional-outcomes-are-a-contract-error)).
- **Announce every non-execution.** Timeout, cancellation, and shutdown
  cancellation are reported to the specific caller affected
  ([INV-2](./architecture.md#invariants)).
- **Validate at the boundary.** Configuration is validated at construction with
  actionable messages — a negative concurrency, a zero batch size, or a weight
  limit smaller than every item fails loudly and early.

## Naming

- **`Attempts`, never `Retries`.** The budget includes the initial execution:
  `Attempts = 3` means at most three executions
  ([D-010](./decisions.md#d-010-the-retry-budget-is-named-attempts-and-includes-the-initial-execution)).
- **Say what is counted.** `maxQueued`, `maxBatchSize`, `maxBatchWeight`,
  `concurrency` — not `limit`, `size`, or `max`.
- **Timeouts name their stage**: pre-admission, queue-wait, execution. "Timeout"
  alone is never a parameter name
  ([queue-and-admission.md § Timeout stages](./subsystems/queue-and-admission.md#timeout-stages)).
- **Booleans read as questions** — `is`, `has`, `should`, `can`.
- **Casing follows the language**, the concept does not: `Attempts` in C#,
  `attempts` in TypeScript, Go, Rust, and Python, same meaning everywhere
  ([INV-13](./architecture.md#invariants)).

## Anti-patterns

| Anti-pattern | Why it is banned |
| --- | --- |
| Required configuration for ordinary use | Breaks progressive disclosure. If it must be set, it needs a default. |
| Requiring a predicate to get retries | The no-predicate path must already work ([D-011](./decisions.md#d-011-retrydecorator-retries-every-ordinary-failure-by-default)). |
| An unbounded queue | Unbounded growth is a memory failure at scale ([INV-3](./architecture.md#invariants)). |
| Dropping the oldest item under pressure | Silent data loss ([INV-1](./architecture.md#invariants)). |
| A sampled worker count that raises the ceiling | The ceiling is the contract ([INV-4](./architecture.md#invariants)). |
| Retrying cancellation | Cancellation is terminal ([INV-5](./architecture.md#invariants)). |
| Holding a slot through backoff | Converts a retry storm into a deadlock ([INV-6](./architecture.md#invariants)). |
| Reviving a dead worker | Keeps the worker state machine honest ([INV-8](./architecture.md#invariants)). |
| `INCR`/`DECR` for distributed counting | Not idempotent under retry ([INV-11](./architecture.md#invariants)). |
| A hard Redis dependency | An outage must degrade accuracy, not availability ([D-083](./decisions.md#d-083-a-redis-outage-fails-open-to-local-continuation)). |
| An OTel or logging dependency in core | Core carries zero observability dependencies ([D-091](./decisions.md#d-091-otel-is-a-separate-opt-in-package-per-language)). |
| `sleep` in a test | Non-deterministic and slow. Inject the clock ([testing.md](./testing.md#deterministic-time)). |
| Divergent semantics "because the language is different" | Only surfaces differ ([INV-13](./architecture.md#invariants)). |
