# Methodology v0.1

## What is measured

Failover Bench measures what a *caller* experiences when the provider behind a gateway or SDK misbehaves, and what the *provider* experiences from that gateway while it happens. Nothing inside the system under test is inspected. Two views are combined:

1. **The caller's view** — the adapter's result: did the call end, when, with what content, which model was reported, was a usage block present, or what error.
2. **The provider's view** — the wall's request log: every attempt that reached the fake provider, its model, its timestamp to the millisecond, and the fault applied.

## The fault catalogue

Sixteen scenarios (`scenarios/catalogue.yaml`). Each names a fault, a plain-language description of correct behaviour, the real-world bug or incident that motivated it, and a list of machine checks. Faults are selected by model name so every system can be pointed at the wall with ordinary configuration and no special headers.

Every healthy completion is the same sixty-word canonical text. Completeness is checked by exact comparison after whitespace normalisation.

## Timing profiles

`full` is the published profile: 20 s first-token delay (S07), 30 s stall (S09), 120 s silence (S06), 60 s outage (S15), 15 ms between tokens. `fast` shortens those for local development and is never used for a published scorecard.

## Scoring a cell

Rescue is decided by the scenario's ideal outcome: for fifteen scenarios the caller should receive the complete canonical answer; for S13 (content-filter rejection) the caller should receive a clean error.

- **pass** — rescued and every check passed.
- **partial** — rescued, but an advisory check failed; or, for S13, the system answered by routing around the rejection.
- **safe** — not rescued, but the call ended with a bounded, clean error and every required check passed.
- **fail** — a hang (no result inside the scenario's `max_wall_s`), a truncated answer presented as success, or any required check failed.

Checks marked `requires: fallback` are reported as n/a for systems that declare no fallback capability, so an SDK is judged on its own promises. Checks marked `informational` never affect the verdict.

Each system's capabilities and parameters are declared in `systems/<name>.yaml` and printed with its results. Defaults are the vendor's defaults except where a run must be bounded (e.g. a 600 s SDK timeout lowered to 30 s), and every such change is stated.

## Sequence scenarios

S15 sends twenty requests four seconds apart across a sixty-second outage. Scored: no request hung; requests during the outage were answered (via the fallback); the primary was used again within thirty seconds of recovering; and, informationally, how many primary attempts were made per request during the outage (a circuit breaker makes this number small).

## The alive probe

After every scenario the runner sends one healthy `fb-ok` request through the same system with a ten-second limit. A system that is still spinning, holding a poisoned connection, or crashed fails `alive_after` where the scenario scores it.

## Publication

A scorecard is published on the first Monday of every month from a `full` run of every listed system on the same machine and the same wall build. Raw JSON results, the wall log excerpt for each cell, and the exact configuration ship with it. Vendors receive each failing scenario as an issue with a one-command reproduction at least seven days before publication. Methodology changes bump this document's version; verdicts from different versions are never compared in one table.

## Known limits

- Hosted-only gateways cannot be pointed at a fake provider and are out of scope.
- Faults are injected at the provider; network faults between the caller and the gateway are not modelled.
- One request per scenario (twenty for S15). Statistical spread across repeated runs is future work.
- The canonical answer is fixed, so systems that cache responses must have caching disabled for the run; this is stated per system.
