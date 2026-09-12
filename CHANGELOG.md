# Changelog

Next scorecard: **Monday 5 October 2026** (methodology v0.1, profile `full`).

## 2026-09-08 — 0.2.0 (unreleased)
- Shareable images: `chart scorecard` (the grid as a PNG, glyph + colour per cell), `chart timeline` (one scenario, one or more runs, as bars on a seconds axis from the wall's log), `chart explainer` (how a measurement works). `site` writes the scorecard and the explainer into docs/ when matplotlib is installed (`.[charts]`) and points `og:image` at the explainer, which keeps its shape in a link preview where the tall grid would be cropped.
- Public scorecard page: `python -m failoverbench site` → docs/index.html, published with GitHub Pages at https://failoverbench.github.io/failoverbench/.
- The shared client treats an in-band SSE error event (a gateway that already sent 200 and partial content) as the error it is, never as a truncated success; regression test added. The LiteLLM proxy row was re-run: its four stream cells moved from fail to safe, matching the in-process Router.
- S06 scored as *unbounded* rather than *hang* when a system retries a silent provider (max_wall_s 60 → 130); catalogue reworded.
- New systems: Bifrost v2.1.0 (Docker, per-request fallbacks), Portkey Gateway OSS (Docker, per-request x-portkey-config), LangChain ChatOpenAI + with_fallbacks, a tuned LiteLLM Router row (allowed_fails + cooldown_time), and an experimental DeepSeek Harness + dsh-llm-fallbacks row through the Python SDK.
- Endpoint adapter: `model_format`, `extra_body` and `headers_json` with `{primary}` / `{fallback}` placeholders; fallback-bearing entries are dropped for calls without a fallback.
- Methodology: the baseline configuration (2 retries, 30 s timeout, one fallback) is now stated explicitly.
- S06 made consistent with that baseline: the required check is now "ends within the configured budget" (100 s = two 30 s retries plus slack) and "did not retry the silent route" is advisory. Under the old 45 s bound every system that obeyed its own configured retries failed; now a system that retries a silent route scores partial (rescued) or safe (not rescued), and only a system whose timeout never fires (a hang past 130 s) fails.
- DSH adapter: a fresh session per request by default, so a session that keeps a replaced model cannot be mistaken for a circuit that never probes.
- S12 no longer fails a compacting retry: the wall logs the prompt size of every attempt, and the check (`context_retry_discipline`) accepts a retry that is strictly smaller than the one before it while still failing a same-size resend. Runs made before the size was logged keep their old verdict rather than gaining from the gap.
- `run --only … --merge` splices a partial re-run into the existing results file (recorded under `reruns`); `rescore` re-evaluates stored results against the current catalogue without touching measurements. New tests in `tests/test_scoring.py`.
- DSH homes now list `CONTEXT_WINDOW_EXCEEDED` in the plugin's `triggerCodes`; without it the plugin never sees a context-length rejection (see the S12 row).

## 2026-09-07 — 0.1.0
- The wall: fake OpenAI-compatible provider, sixteen faults selected by model name, request log with millisecond timings, TCP reset / cut / stall / malformed / no-[DONE] stream faults, prefill continuation.
- The runner: hard deadlines (a hang is a result), alive probe after every scenario, sequence mode for the flapping primary, verdicts pass / partial / safe / fail.
- Adapters: direct (control), reference client, openai-python, litellm-router, generic OpenAI-compatible endpoint.
- First fast-profile run: control row and reference client (results/fast is git-ignored; the published run uses `full`).
