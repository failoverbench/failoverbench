# Changelog

Next scorecard: **Monday 5 October 2026** (methodology v0.1, profile `full`).

## 2026-09-07 — 0.1.0
- The wall: fake OpenAI-compatible provider, sixteen faults selected by model name, request log with millisecond timings, TCP reset / cut / stall / malformed / no-[DONE] stream faults, prefill continuation.
- The runner: hard deadlines (a hang is a result), alive probe after every scenario, sequence mode for the flapping primary, verdicts pass / partial / safe / fail.
- Adapters: direct (control), reference client, openai-python, litellm-router, generic OpenAI-compatible endpoint.
- First fast-profile run: control row and reference client (results/fast is git-ignored; the published run uses `full`).
