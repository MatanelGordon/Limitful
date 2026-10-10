# RedisSynchronizationProvider

Redis-specific technical design for a concrete
[`SynchronizationProvider`](../utilities/synchronization-provider.md). Limitful
controllers depend only on the backend-neutral provider contract and its
capabilities; they never name Redis or receive a Redis adapter
([D-163](../decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract)).

This document owns the Redis implementation mechanics: identity sets, keys,
scripts, liveness, cluster slotting, outage detection, and recovery. It does not
define a competing generic coordination API
([D-164](../decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)).

- [Scope](#scope)
- [Set-based counting](#set-based-counting)
- [Liveness](#liveness)
- [Degraded and fail-open behavior](#degraded-and-fail-open-behavior)
- [The Redis adapter](#the-redis-adapter)
- [Cluster compliance](#cluster-compliance)
- [Defaults](#defaults)
- [Advanced options](#advanced-options)
- [Invariants](#invariants)
- [Test coverage](#test-coverage)
- [Open items](#open-items)

## Scope

In-process operation is the default. A compatible utility opts into
cross-instance coordination by receiving a `SynchronizationProvider`; choosing
this implementation makes that provider Redis-backed. Several utilities may
share one provider instance, but no utility is coordinated merely because
another utility uses Redis.

| Owns | Does not own |
| --- | --- |
| Redis representation of idempotent membership, claims, and count-like state | The backend-neutral semantic contract or capability names |
| The liveness protocol: heartbeat, last-seen, peer disqualification | Any specific Redis client library |
| Redis outage detection, recovery, and divided-allocation fallback | A universal outage policy for every controller |
| Key naming, prefixing, scripts, and deliberate hash-slot design | Durable job storage or cross-process payload transfer ([INV-14](../architecture.md#invariants)) |

The provider coordinates **permission and shared state**, not work. A job
submitted to one process is always executed by that process. For
divided-allocation modes, Redis tells each process how much of a shared allowance
is its local share. Atomic-claim modes use Redis scripts/transactions to grant or
deny permission directly.

The provider declares only capabilities it can satisfy under the configured
deployment. A controller whose required capability is absent fails configuration
before accepting work
([D-150](../decisions.md#d-150-providers-declare-capabilities-and-insufficient-providers-fail-configuration)).

## Set-based counting

**Never use increment/decrement** — that loses idempotency on retry
([D-082](../decisions.md#d-082-distributed-counting-is-set-based-never-increment-or-decrement),
[INV-11](../architecture.md#invariants)).

Each counted entity has a specific ID and joins a Redis **set**. To release — a
`ParallelWorker` retiring itself, for instance — it removes **its own ID** from
the set. The effective count is the **cardinality of the set**, which is far more
accurate and retry-safe than a mutated number.

Why this matters: a dropped acknowledgement on an `INCR` leaves the counter
permanently wrong, and a retried `DECR` double-counts. Adding or removing a known
ID is idempotent, so any command can be retried safely.

## Liveness

A distributed, self-cleaning protocol keeps stale IDs from crashed instances from
inflating the set forever
([D-086](../decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol)):

1. **Graceful removal on clean death.** A process that dies cleanly signals Redis
   to remove its set members. This is part of ordered disposal
   ([architecture.md § Lifecycle](../architecture.md#lifecycle-and-disposal)).
2. **Heartbeat / keep-alive service.** Enabling Redis for any utility starts a
   heartbeat on a user-configurable interval that periodically refreshes a
   keep-alive.
3. **Last-seen timestamp plus peer disqualification.** A separate key stores each
   member's last keep-alive time. Workers periodically scan the sets and
   disqualify any member whose keep-alive has gone stale.

The third step is **fully distributed**: any worker can prune dead peers, so
there is no single reaper and no leader election, and the set stays frequently and
accurately updated.

```mermaid
sequenceDiagram
  autonumber
  participant A as Process A
  participant R as Redis
  participant B as Process B

  A->>R: add own ID to the membership set
  B->>R: add own ID to the membership set
  A->>R: refresh last-seen on the heartbeat interval
  B->>R: refresh last-seen on the heartbeat interval
  A->>R: read set cardinality, about once per minute
  R-->>A: 2 members
  Note over A: Local share equals N divided among 2

  Note over B: Process B crashes without signalling
  A->>R: liveness scan - read members and last-seen together
  R-->>A: B last seen beyond the staleness threshold
  A->>R: remove B's ID - any peer may prune, no single reaper
  A->>R: read set cardinality
  R-->>A: 1 member
  Note over A: Local share equals all of N
```

## Degraded and fail-open behavior

The provider reports healthy, degraded/uncertain, and recovered state through the
neutral contract. The owning utility applies its documented degraded policy.
This provider's historical fail-open behavior is retained specifically for
**divided-allocation mode** when a finite local share was allocated before the
outage
([D-164](../decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)).

Each process samples the active worker/process count periodically — roughly once
per minute. If Redis becomes unavailable, the process **keeps running** and uses
the **last sampled count** to divide the global allowance locally until Redis
recovers.

Slow membership changes may cause a gradual, **bounded overshoot** of the global
ceiling. That tradeoff is accepted deliberately for this mode, and it is the
documented Redis divided-allocation exception to `RateController`'s hard
coordinated ceiling
([INV-4](../architecture.md#invariants),
[rate-controller.md](../utilities/rate-controller.md#the-ceiling-and-the-worker-count)).

This is not a generic promise for atomic global claims or time-based quotas. A
controller that requires authoritative coordination time or an atomic global
reservation follows its own documented outage policy. In particular,
`ThroughputController` partition behavior remains unresolved; the provider must
never copy an entire last-known global reservoir into every process or report a
local approximation as a hard global guarantee.

```mermaid
stateDiagram-v2
  [*] --> Coordinated

  state Coordinated {
    [*] --> Sampling
    Sampling --> Sampling: read set cardinality, about once per minute
    Sampling --> Allocated: divide N by the live member count
    Allocated --> Sampling: next sample
  }

  Coordinated --> Degraded: Redis unavailable

  state Degraded {
    [*] --> UseLastSample
    UseLastSample --> FrozenPolicy: frozen membership - default-defined behavior
    UseLastSample --> NonFrozenPolicy: non-frozen membership - behavior deferred

    state FrozenPolicy {
      [*] --> Baseline
      Baseline --> Baseline: new workers add no capacity
      Baseline --> Reduced: a removal may only reduce the allocation
      Reduced --> Reduced: never increases again while degraded
    }
  }

  Degraded --> Coordinated: Redis recovers, resume sampling

  note right of Degraded
    The application keeps running - D-083.
    Bounded overshoot of the global ceiling
    is accepted: the one exception to INV-4
  end note
  note right of NonFrozenPolicy
    Supported as a configuration choice,
    exact behavior is an open item
  end note
```

### Membership policy during an outage

Configurable
([D-084](../decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined)):

| Policy | Behavior |
| --- | --- |
| **Frozen membership** | Treat the last sampled count as the baseline. Do not add capacity or account for newly appearing workers. Removals may **only reduce** the effective capacity/allocation, never increase it |
| **Non-frozen membership** | Supported as a configuration choice; its exact behavior is **deferred** — see [open items](#open-items) |

Frozen membership is the conservative policy: it can only shrink a process's
share while blind, so overshoot stays bounded by the membership drift that
occurred during the outage.

## The Redis adapter

**The Redis provider does not bundle or control a specific Redis client.** Users
construct `RedisSynchronizationProvider` with a Redis-specific adapter describing
how to connect and execute commands/scripts, so any client can back the provider
([D-085](../decisions.md#d-085-redis-access-goes-through-a-user-supplied-adapter)).

The adapter is private to the concrete provider boundary. It is never accepted by
`RateController`, `ThroughputController`, or another controller API.

> Illustrative pseudocode. No public API signature is committed yet.

```text
provider = redisSynchronizationProvider({
  adapter: {
    execute: (command, keys, args) => myClient.send(command, keys, args),
    # plus whatever each binding needs for multi-key and scripted operations
  },
  keyPrefix: "myapp:limitful",
  heartbeatInterval: seconds(10),
  stalenessThreshold: seconds(45),
  membershipDuringOutage: Membership.Frozen,
})
```

The adapter is also the **test seam**: an in-memory fake adapter, driven by an
injected clock, makes outage, recovery, and stale-peer pruning fully
deterministic ([testing.md § Test doubles](../testing.md#test-doubles-and-override-points)).

## Cluster compliance

**Cluster compliance is a hard requirement**
([D-087](../decisions.md#d-087-cluster-compliance-requires-deliberate-selective-slotting-and-a-user-prefix)).

1. **Key slotting is designed deliberately.** Any operation touching multiple keys
   together — multi-get, multi-key commands, transactions, scripts — must ensure
   those keys land in the **same hash slot**, using hash tags so related keys
   co-locate. **Every multi-key operation is an explicit slotting design point and
   must be called out, not assumed.**
2. **User-defined key prefix.** The user can define a prefix for all Limitful keys,
   so the library coexists with a Redis instance used for other purposes without
   clobbering anything. The prefix also lets multiple rate controllers and
   mechanisms across multiple services intentionally **share or isolate**
   coordination as desired.
3. **Slot selectively, not globally.** Keys only ever touched on their own slot
   **naturally** — let Redis place them, no hash tag needed, since there is no
   batched or multi-key operation on them. Impose explicit hash-tag slotting
   **only** where an operation genuinely reads multiple keys together, such as the
   liveness scan, where a worker checks which peers have died without signalling.

| Operation | Keys touched together | Slotting |
| --- | --- | --- |
| Join / leave membership | One set key | Natural |
| Read effective count | One set key | Natural |
| Heartbeat refresh | One last-seen key | Natural |
| **Liveness scan** | Membership set **and** last-seen keys | **Deliberate** — must co-locate |

**Open item.** Whether the membership set and the last-seen timestamp key share a
hash tag (co-locate) or stay independent is **not yet decided** — it depends on
the final counting mechanism. The distinction between deliberately slotted and
naturally slotted keys is important and must be resolved once that mechanism is
designed.

## Defaults

| Option | Default | Notes |
| --- | --- | --- |
| Synchronization provider | **None** | In-memory, in-process, zero dependencies ([D-163](../decisions.md#d-163-synchronizationprovider-is-the-backend-neutral-public-contract)) |
| Redis adapter | None | Required to construct this concrete provider |
| Key prefix | `Undecided` | A library-identifying default is expected. Surfaced during consolidation |
| Count sampling interval | About once per minute | ([D-083](../decisions.md#d-083-a-redis-outage-fails-open-to-local-continuation)) |
| Heartbeat interval | User-configurable, no value chosen | ([D-086](../decisions.md#d-086-liveness-is-a-distributed-self-cleaning-protocol)) |
| Staleness threshold | `Undecided` | Must exceed the heartbeat interval by a safe margin. Surfaced during consolidation |
| Outage membership policy | `Undecided` | Frozen is fully defined; which policy is the default is not ([D-084](../decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined)) |
| Divided-allocation outage behavior | Fail open from the finite last share | Applies only to compatible divided-allocation consumers; other utilities own their degraded policy ([D-164](../decisions.md#d-164-redis-coordination-is-a-concrete-provider-under-the-neutral-contract)) |

## Advanced options

| Option | Shape | Effect |
| --- | --- | --- |
| Adapter | injected interface | Any Redis client, or a fake in tests |
| Key prefix | string | Coexistence, and deliberate sharing or isolation across services |
| Heartbeat interval | duration | Liveness refresh frequency |
| Staleness threshold | duration | When a peer becomes disqualifiable |
| Sampling interval | duration | How often the global count is re-read |
| Outage membership policy | enum | Frozen or non-frozen |
| Clock | injected | Deterministic heartbeat, staleness, and outage tests |

## Invariants

- Counting is set-based and idempotent; `INCR`/`DECR` is never used
  ([INV-11](../architecture.md#invariants)).
- An entity only ever removes **its own** ID, except through the explicit
  staleness-based peer disqualification path.
- In divided-allocation mode, a Redis outage continues from the finite last
  sampled share and reports degraded state.
- No degraded path is described as a hard global guarantee.
- Under frozen membership, a degraded process's allocation never grows.
- Overshoot during an outage is bounded by membership drift, not unbounded.
- Every multi-key operation has a documented, deliberate slot design.
- All keys carry the user-configured prefix.
- Clean shutdown removes membership before disposal completes.

## Test coverage

Case IDs `RDS-xxx` in
[testing.md § RedisSynchronizationProvider](../testing.md#redissynchronizationprovider-rds).
All of them run against a **fake in-memory adapter plus an injected clock** — no
real Redis in the business suite. A binding may additionally run an integration
suite against a real cluster as a technical test.

## Open items

| Item | Status |
| --- | --- |
| The non-frozen membership policy and which policy is the default | Not decided ([D-084](../decisions.md#d-084-membership-during-an-outage-is-configurable-frozen-is-defined)) |
| Whether the membership set and the last-seen key co-locate under one hash tag | Not decided, pending the final counting mechanism ([D-087](../decisions.md#d-087-cluster-compliance-requires-deliberate-selective-slotting-and-a-user-prefix)) |
| How `N` is divided across processes, including integer remainders and whether every process may round up | Not decided |
| The exact adapter interface, including how multi-key and scripted operations are expressed across clients | Not decided. Surfaced during consolidation |
| Default key prefix, heartbeat interval, and staleness threshold | Not decided. Surfaced during consolidation |
| Whether one Redis provider instance may coordinate several scopes atomically, and how multi-scope operations are ordered | Not decided ([synchronization-provider.md](../utilities/synchronization-provider.md#open-design-questions)) |
