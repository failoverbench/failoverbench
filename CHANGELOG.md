# Changelog

Next scorecard: **Monday 5 October 2026** (methodology v0.1, profile `full`).

## 2026-09-08 — 0.2.0 (unreleased)
- Public scorecard page: `python -m failoverbench site` → docs/index.html, published with GitHub Pages at https://failoverbench.github.io/failoverbench/.
- The shared client treats an in-band SSE error event (a gateway that already sent 200 and partial content) as the error it is, never as a truncated success; regression test added. The LiteLLM proxy row was re-run: its four stream cells moved from fail to safe, matching the in-process Router.
- S06 scored as *unbounded* rather than *hang* when a system retries a silent provider (max_wall_s 60 → 130); catalogue reworded.
- New systems: Bifrost v2.1.0 (Docker, per-request fallbacks), Portkey Gateway OSS (Docker, per-request x-portkey-config), LangChain ChatOpenAI + with_fallbacks, a tuned LiteLLM Router row (allowed_fails + cooldown_time), and an experimental DeepSeek Harness + dsh-llm-fallbacks row through the Python SDK.
- Endpoint adapter: `model_format`, `extra_body` and `headers_json` with `{primary}` / `{fallback}` placeholders; fallback-bearing entries are dropped for calls without a fallback.
- Methodology: the baseline configuration (2 retries, 30 s timeout, one fallback) is now stated explicitly.

## 2026-09-07 — 0.1.0
- The wall: fake OpenAI-compatible provider, sixteen faults selected by model name, request log with millisecond timings, TCP reset / cut / stall / malformed / no-[DONE] stream faults, prefill continuation.
- The runner: hard deadlines (a hang is a result), alive probe after every scenario, sequence mode for the flapping primary, verdicts pass / partial / safe / fail.
- Adapters: direct (control), reference client, openai-python, litellm-router, generic OpenAI-compatible endpoint.
- First fast-profile run: control row and reference client (results/fast is git-ignored; the published run uses `full`).
