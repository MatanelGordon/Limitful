# Limitee — Q&A Round 3

> **Historical record. Consolidated 2026-10-03.** Every decision below has been
> migrated into [docs/decisions.md](./docs/decisions.md) as a `D-nnn` record and
> into the relevant design document under [docs/](./docs/README.md). This file is
> kept for provenance — the questions show *why* each decision was needed. Cite
> the `D-nnn` record, not this transcript, and record new decisions there rather
> than editing this file.
>
> Mapping: Q1 → D-083, D-084 · Q2 → D-002 · Q3 → D-070, D-071 · Q4 → D-013, D-014
> · Q5 → D-015, D-016 · Q6 → D-012 · Q7 → D-011 · Q8 → D-010 · Q9 → D-040, D-041,
> D-046 · Q10 → D-042 · Q11 → D-043 · Q12 → D-044 · Q13 → D-045 · Q14 → D-036,
> D-037 · Q15 → D-035 · Q16 → D-035 · Q17–Q19 → D-046, D-047, D-048 · Q20 → D-030
> · Q21 → D-031, D-032 · Q22 → D-033 · Q23 → D-034 · Q24 → D-062 · Q25 → D-063.

Design decisions captured during the third grilling round. Final decisions are stated directly; remaining deferred details are called out explicitly. The user will migrate the desired material into `CLAUDE.md`.

## 1. Redis outage contract — availability vs global ceiling

**Q:** During a Redis outage or network partition, should each instance continue locally, accepting that the global concurrency ceiling may be exceeded, or should Limitee stop admitting new work to preserve that ceiling?

**A:** Choose **fail-open local continuation**. Redis must not become a dependency whose outage disables the application. Each process periodically samples the active worker/process count, roughly once per minute. If Redis becomes unavailable, it initially uses the last sampled count to divide the global allowance locally. Slow membership changes may cause a gradual, bounded overshoot; that tradeoff is accepted.

Membership handling during Redis unavailability is configurable:

1. **Frozen membership:** Treat the last sampled count as the baseline. Do not add capacity or account for newly appearing workers. Removals may only reduce the effective capacity/allocation; they never increase it.
2. **Non-frozen membership:** Supported as a configuration choice, but its exact behavior is deferred.

## 2. RateController ceiling vs adaptive worker count

**Q:** When RateController uses ParallelWorkers, is RateController's configured N always the hard in-flight ceiling, with any worker-count value requested by the sampling function clamped to N?

**A:** During normal coordinated operation, RateController's configured N is the hard global in-flight ceiling. The sampled worker count only divides that fixed budget among workers; it must not increase the total amount of allowed in-flight work. The fail-open Redis-outage behavior in Question 1 is the explicit exception where temporary bounded overshoot is accepted.

## 3. Cancellation-mode disposal vs processing guarantee

**Q:** Is cancellation-mode disposal an explicit exception to the guarantee that every queued job is processed, with queued jobs that have not started completing as cancelled instead of being executed?

**A:** Shutdown behavior is configurable. In both modes, stop accepting new enqueues immediately; attempts made after shutdown begins fail with cancellation.

1. **Drain:** Allow jobs already in the queue to finish processing, then dispose.
2. **Cancel pending:** Cancel every queued-but-not-started job. Jobs already executing are not included in this cancellation instruction and may finish under their normal behavior.

**Deferred/open:** The disposition of callers already awaiting insertion when shutdown begins is not yet specified.

## 4. Retry backoff and concurrency-slot ownership

**Q:** When a retry-decorated function runs as a RateController job, does that one logical job keep its in-flight concurrency slot across every attempt and the delays between attempts?

**A:** A failed attempt must not retain its in-flight slot during backoff. Support two retry API styles:

1. An **awaited retry path**.
2. A **deferred fire-and-forget retry path** that places failed work into a delayed/dead-letter-style queue and reports ultimate success or failure through an event.

**Deferred/open:** The exact API shape and naming are undecided. The distinction between a delayed retry queue and terminal dead-letter storage is also not yet defined.

## 5. Awaited retry re-admission

**Q:** After backoff in the awaited retry path, should each later attempt re-enter normal admission and acquire a new in-flight slot, or bypass admission?

**A:** Awaited retries re-enter normal admission rather than bypassing it. Retry scheduling priority is configurable:

1. **Full retry prioritization:** The retry jumps ahead.
2. **No prioritization:** Normal queued work goes first.
3. **Probabilistic prioritization:** A configurable probability X determines whether a retry jumps ahead.

The goal is to allow timely retries without starving normal queued jobs.

**Deferred/open:** When a retry re-enters a full bounded queue, the applicable overflow behavior is not yet defined. Exact arbitration and starvation guarantees for the three priority modes are also deferred.

## 6. Cancellation during awaited retries

**Q:** When cancellation arrives during an awaited retry, is it always terminal—interrupting backoff and preventing future attempts—or may the user's retry predicate choose to retry cancellation?

**A:** Cancellation is always terminal. It immediately stops retry/backoff and must not be overridden by the retry predicate.

## 7. Default retry trigger

**Q:** If the user supplies no retry predicate, should RetryDecorator retry every ordinary failure except cancellation, or require explicit retry conditions and otherwise not retry?

**A:** RetryDecorator must provide a simple, friendly default for ordinary users. By default, retry every ordinary failure automatically; cancellation remains terminal and is never retried. A simple fixed delay, such as 100 ms, should be easy to configure without defining predicates. Advanced users may opt into complex, explicit retry conditions.

**Deferred/open:** The default `Attempts` value, default delay/backoff and jitter, and the cross-language definition of an "ordinary failure" are not yet specified. The 100 ms value above is an ease-of-configuration example, not a chosen default.

## 8. Attempt-count semantics

**Q:** If the configured attempt count is 3, does that mean three total executions—the initial call plus two retries—or three retries after the initial call, for four executions total?

**A:** Expose a **total-attempts** setting, not a retry-count setting. The number includes the initial execution; for example, 3 means at most three executions overall.

**Addendum:** Name the public configuration field or parameter **`Attempts`**, or use equivalent total-attempts wording. Never name it **`Retries`** or describe it as a retry count. It includes the initial execution.

## 9. AsyncAccumulator batch-handler contract

**Q:** Does AsyncAccumulator invoke one user-supplied function with the entire batch and receive an outcome for each input, or invoke each item's function separately while merely starting the items together?

**A:** AsyncAccumulator uses a true batch function. It accumulates inputs into batches and invokes one batch operation per batch, returning per-input outcomes. Its batching concurrency is implemented through the library's **ParallelWorkers** utility, whose long-lived looping batching workers accumulate queued items and invoke the provided batch function repeatedly. AsyncAccumulator does **not** directly integrate with or submit work to RateController. The caller may independently wrap the function with RateController in whichever composition order they choose; that is user composition, not AsyncAccumulator's responsibility.

## 10. Batch outcome correlation

**Q:** How should the batch function's per-input outcomes map back to callers: by a same-length positional sequence matching input order, or by explicit per-item keys/IDs?

**A:** Default to positional input/output correlation. Offer an advanced keyed/ID-based correlation option for callers who need reordered or partial-result handling.

**Deferred/open:** The exact C# API and keyed-correlation edge cases—missing, duplicate, or unknown keys—are intentionally deferred.

## 11. Positional result-count mismatch

**Q:** In positional mode, if the batch function returns a different number of outcomes than inputs, should the entire batch fail as a contract violation, or should available outcomes be delivered while only unmatched inputs fail?

**A:** If positional mode returns fewer outcomes than inputs, deliver every matching positional outcome normally and fail only the unmatched inputs. Do not fail the entire batch. Surplus outcomes are handled separately in Question 12.

## 12. Surplus positional outcomes

**Q:** If positional mode returns more outcomes than there were inputs, should the surplus outcomes be ignored, or should the batch surface a contract error even though every input received an outcome?

**A:** If positional mode returns surplus outcomes beyond the submitted inputs, surface a contract error; do not silently ignore them.

**Deferred/open:** Where that contract error is surfaced, and whether it changes the already matched callers' outcomes, are not yet defined.

## 13. Batch-function exception fan-out

**Q:** If the batch function throws instead of returning per-input outcomes, should every input in that batch complete with the same batch-level failure?

**A:** If the batch function throws before returning results, every input in that batch completes with the same batch-level failure.

## 14. Waiting-to-batch timeout terminality

**Q:** When an item reaches its waiting-to-batch timeout, is it removed and guaranteed never to execute, or does only the caller stop waiting while the item may still be processed later?

**A:** When an item times out while waiting to batch, remove it from the accumulator and guarantee that it will never execute later.

**Cancellation clarification:** If AsyncAccumulator detects that a queued item's main task has been cancelled, that item must not run at all, even if it still physically resides in the queue.

**Deferred/open:** The exact atomic race rule when timeout/cancellation and execution claim happen concurrently is not yet defined.

## 15. Batch-processing timeout and running work

**Q:** When a batch-processing timeout expires, should Limitee signal cancellation to the running batch function, or only time out the callers while allowing the function to continue running?

**A:** An execution timeout must signal cancellation to the running batch function. Keep these lifecycle concepts distinct:

1. **Pre-admission timeout:** An optional, user-configured timeout before an item gains entry to the queue.
2. **Queue-wait timeout:** Applies while an item waits under backlog. On timeout, remove it and guarantee no later execution.
3. **Execution timeout:** Applies once work is running. On timeout, signal cancellation to the batch function.
4. **Possible separate batch-function timeout:** A distinct policy question, addressed in Question 16.

The accumulation interval in Questions 17–19 is batching/scheduling behavior, not one of these failure timeouts.

## 16. Separate batch-function timeout

**Q:** Should AsyncAccumulator expose a separate timeout for the entire batch function, distinct from per-item execution timeout, or should the batch function have no separate library-enforced timeout?

**A:** Timeout scopes are distinct across lifecycle stages. Once an item is dequeued into a batch and execution begins, its queue-wait timeout no longer applies; the execution/batch timeout policy takes over.

**Deferred/open:** This round did not decide whether AsyncAccumulator exposes a separate whole-batch function timeout, whether execution deadlines are batch-wide or per item, or the behavior when user code ignores a cancellation signal.

## 17. Batch-timer anchor

**Q:** Is the batch interval measured from the first item entering a new batch, reset after every new arrival as a debounce, or run on a fixed global cadence?

**A:** AsyncAccumulator batching runs under ParallelWorkers. ParallelWorkers provides long-lived, looping batching workers. While queued work remains, a worker invokes consecutive batches immediately. Once the queue is empty, no countdown starts until the first new item arrives; that item starts the full configured accumulation interval described in Question 19.

## 18. Per-worker interval scheduling

**Q:** For each looping batching worker, does the next batching interval begin only after its previous batch function completes, or does it follow a fixed cadence independent of batch-processing duration?

**A:** There is no fixed cadence while backlog remains. After a batch completes, fire subsequent batches immediately while queued work remains. If the queue is empty, wait for the first new item; its arrival starts the configured accumulation interval.

## 19. Empty-queue interval anchor

**Q:** When the queue becomes empty, does the batching-interval countdown start immediately, or does it start only when the first new item arrives so that item gets the full interval to accumulate peers?

**A:** When idle, begin the configured accumulation interval only when the first new item arrives, so it receives the full window to collect peers. If the batch still has room, keep waiting within that window for more items before invoking it. The exact low-level implementation may be language-dependent.

**Implementation guidance:** Use event-driven waiting when the language supports it—for example, await the next item from a C# Channel. Where polling is necessary, poll using the same configured batching interval.

**Deferred/open:** Polling latency semantics and ownership of the first-item accumulation window when multiple batching workers are idle are not yet defined.

## 20. Full-queue reject semantics

**Q:** When a bounded queue is full, should reject mode fail the new enqueue immediately, making await-insertion the only overflow mode that waits for space?

**A:** When a bounded queue is full, fail insertion immediately by default. Waiting for space is available only through an explicit await-insertion mode.

## 21. Await-insertion waiter bound

**Q:** In await-insertion mode, should Limitee cap the number of callers waiting outside the full queue, or may any number wait with that memory/backpressure responsibility left to the caller?

**A:** Keep the default API simple: full queues fail immediately. Advanced callers may explicitly await insertion and compose their own upstream controls, such as web-controller or middleware rate limiting. That added complexity, including any unbounded admission waiters, remains the caller's responsibility; Limitee does not cap those waiters.

## 22. Await-insertion fairness

**Q:** Should callers awaiting insertion be admitted strictly FIFO, with new enqueue attempts unable to bypass existing waiters?

**A:** This concerns callers who explicitly choose to await insertion into a full queue. Do not guarantee strict FIFO. Admission order is implementation-dependent because FIFO adds unnecessary complexity and is not required.

## 23. Cancellation while awaiting insertion

**Q:** If a caller cancels while awaiting insertion into a full queue, must that pending insertion be removed immediately and guaranteed never to enter the queue later?

**A:** Cancellation while awaiting insertion immediately removes the pending request and guarantees that it never enters the queue later.

**Deferred/open:** The exact atomic rule when admission and cancellation become ready concurrently is not yet defined.

## 24. GrouppedRateController global ceiling

**Q:** Should GrouppedRateController enforce one global concurrency ceiling across all groups in addition to each group's own limit, or should groups be fully independent so total concurrency may reach the sum of their limits?

**A:** GrouppedRateController enforces both numeric per-group concurrency limits and a numeric shared global concurrency ceiling.

**Allocation requirement:** Normalize allocation of the shared global capacity relative to both the number of active/contending groups and the global worker/slot count. The exact normalization algorithm is not yet defined.

**Deferred/open:** The exact public API shape, definition of an active/contending group, unused-capacity redistribution, and integer remainder handling are not yet defined.

## 25. Scheduling groups under the shared ceiling

**Q:** When several groups have queued work and a shared global slot opens, should the next group be chosen by global item FIFO, fair rotation across groups, or configurable group priority?

**A:** Use fair rotation among competing groups by default. Support caller-assigned group priorities as an advanced API option.

**Deferred/open:** The exact fair-rotation algorithm and how advanced priorities interact with fairness are not yet defined.

## Deferred and open details

- **Redis fallback (Q1):** Define the non-frozen membership policy and its default.
- **Shutdown (Q3):** Define what happens to callers already awaiting insertion when shutdown begins.
- **Retries (Q4–Q8):** Finalize API shape/naming, delayed-retry versus dead-letter semantics, full-queue re-admission behavior, default `Attempts`, default delay/backoff/jitter, ordinary-failure classification, and priority arbitration.
- **Batch outcomes (Q10–Q12):** Finalize keyed-correlation edge cases, the C# surface, and how surplus-result contract errors are delivered.
- **Timeouts and cancellation (Q14–Q16, Q23):** Define atomic race boundaries, whether a separate whole-batch timeout exists, whether deadlines are batch-wide or per item, and behavior when user code ignores cancellation.
- **Batching workers (Q17–Q19):** Define ownership of the first-item accumulation window across multiple idle workers and the exact latency semantics of polling implementations.
- **Queue policy scope (Q20–Q23):** State exactly which utilities inherit reject-by-default, uncapped awaiters, implementation-dependent waiter ordering, and cancellation behavior.
- **Grouped allocation (Q24–Q25):** Finalize the public API, normalization/remainder algorithm, active-group definition, spare-capacity redistribution, and advanced-priority algorithm.

## Notes to transfer into `CLAUDE.md`

- Library APIs should be dead simple for beginners by maximizing sensible default behaviors and values. Nuanced behavior should be opt-in through properties or function injection for advanced users.
- Await-insertion is an advanced mode. Callers choosing it are responsible for upstream backpressure and for controlling the number of operations waiting outside Limitee's bounded queue.
- Name the retry budget `Attempts`, or use equivalent total-attempt wording—never `Retries` or retry-count wording. It includes the initial execution.
- AsyncAccumulator uses true batch functions and ParallelWorkers-backed batching workers. It does not directly integrate with RateController; RateController composition belongs to the caller.
- Prefer event-driven waiting for batching where the language supports it. If polling is necessary, use the configured batching interval.
- Document RateController's hard coordinated ceiling together with the explicit fail-open Redis-outage exception, where temporary bounded overshoot is accepted.
