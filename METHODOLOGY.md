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

Each system's capabilities and parameters are declared in `systems/<name>.yaml` and printed with its results.

**Baseline configuration.** Every system is given the same budget so rows are comparable: up to two retries, a 30 s request (or stream-idle) timeout, and one fallback model. Everything else is the vendor's default, and every departure from a default is stated in the system's notes. Where a vendor's default differs from the baseline (Bifrost ships with zero retries; LiteLLM never cools down a single deployment), a second "tuned" or "defaults" row may be added so the difference is visible rather than hidden.

## Context-length rejections (S12)

A request the model cannot fit must never be resent unchanged. One attempt is ideal; an agent harness that compacts its context and retries once is doing the right thing, so a retry is accepted when it is strictly smaller than the attempt before it (the wall records the prompt size of every attempt). A same-size resend, or more than two attempts, fails.

## Sequence scenarios

S15 sends twenty requests four seconds apart across a sixty-second outage. Scored: no request hung; requests during the outage were answered (via the fallback); the primary was used again within thirty seconds of recovering; and, informationally, how many primary attempts were made per request during the outage (a circuit breaker makes this number small).

## The alive probe

After every scenario the runner sends one healthy `fb-ok` request through the same system with a ten-second limit. A system that is still spinning, holding a poisoned connection, or crashed fails `alive_after` where the scenario scores it.

## Which version is scored

The scorecard scores the newest version a reader can install at the time of the run: for a containerised system, the newest released image tag on its public registry; for a library, the newest release on its package index. Pre-release channels, `dev`/`main` tags and source builds are not scored, because a row exists to tell a reader what they will get if they install the thing today.

A fix that lands upstream but has not shipped is still worth measuring, and we do measure it — on a source build, pinned to an exact commit. That measurement is reported to the vendor and recorded in one sentence in the affected row's notes, naming the PR, the commit and what changed. It never moves a verdict. The cell keeps the score the released version earns until a release containing the fix exists, at which point the row is re-run and the note is dropped.

The exact image digest is published for every containerised row — in the row's notes, in the `docker-compose.yml` that produced it, and in the results JSON — so a reader can pull the identical bytes rather than a tag that has since moved. Tags are pinned by digest (`image: name:tag@sha256:…`) for the same reason.

## Publication

A scorecard is published on the first Monday of every month from a `full` run of every listed system on the same machine and the same wall build. Raw JSON results, the wall log excerpt for each cell, and the exact configuration ship with it. Vendors receive each failing scenario as an issue with a one-command reproduction at least seven days before publication. Methodology changes bump this document's version; verdicts from different versions are never compared in one table.

Between scorecards a row may be partly re-run (`run --only … --merge`, after a configuration fix on our side) or re-scored (`rescore`, after a check changes); the results file records both, with timestamps. A re-score never alters a measurement, only how it is judged, and a rule that needs data an older run did not record scores that run as the older rule did rather than in its favour.

## Known limits

- Hosted-only gateways cannot be pointed at a fake provider and are out of scope.
- Faults are injected at the provider; network faults between the caller and the gateway are not modelled.
- One request per scenario (twenty for S15). Statistical spread across repeated runs is future work.
- The canonical answer is fixed, so systems that cache responses must have caching disabled for the run; this is stated per system.
