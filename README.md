# Failover Bench

**A crash-test lab for LLM gateways and SDKs.**

Every gateway says it retries, fails over and never hangs. Failover Bench checks. A fake OpenAI-compatible provider breaks on purpose in sixteen documented ways — rate limits, dead streams, resets, stalls, malformed bytes, a primary that flaps — and every popular gateway and SDK is pushed through the same sixteen faults. The result is one scorecard, refreshed on the first Monday of every month, plus a reproducible bug report to every vendor that fails.

**Next scorecard: Monday 5 October 2026.** Methodology v0.1.

## How it works

1. **The wall** (`python -m failoverbench wall`) is a fake provider. Point anything at `http://127.0.0.1:8401/v1`. The *model name* picks the fault: `fb-ok` always answers; `fb-s08-stream-cut` dies after 40 of 60 tokens; `fb-s15-flap` answers 503 for sixty seconds and then recovers. It logs every attempt it sees, with timings.
2. **The runner** (`python -m failoverbench run`) sends one request per scenario through a system under test — the openai SDK, LiteLLM's Router, a gateway in Docker — under a hard deadline, then combines what the caller got with what the wall saw.
3. **The report** (`python -m failoverbench report`) renders `results/<profile>/SCORECARD.md`.

Every healthy answer is the same sixty-word text, so a truncated stream can never be mistaken for a complete one.

## Quick start

```bash
git clone https://github.com/failoverbench/failoverbench && cd failoverbench
pip install -e .                                   # httpx + pyyaml; openai / litellm only if you test them

python -m failoverbench wall --profile fast -v     # terminal 1: the fake provider (fast = short waits)
python -m failoverbench run --system systems/reference.yaml --profile fast   # terminal 2
python -m failoverbench run --system systems/direct.yaml    --profile fast
python -m failoverbench report --profile fast && open results/fast/SCORECARD.md
```

`--profile full` uses the real waits (20 s first token, 30 s stalls, 60 s outage) and is what the published scorecard runs. A full run of the catalogue takes about ten minutes per system.

## Systems under test

| System | Config | Status |
|---|---|---|
| No gateway — one request, no retries (the control row) | `systems/direct.yaml` | runs |
| Reference client — a small httpx client written to pass | `systems/reference.yaml` | runs |
| openai-python SDK, built-in retries | `systems/openai-python.yaml` | `pip install openai` |
| LiteLLM Router, in-process | `systems/litellm-router.yaml` | `pip install litellm` |
| LiteLLM proxy, Docker | `systems/litellm-proxy.yaml` + `gateways/litellm/` | `docker compose up` |
| Bifrost · Portkey Gateway · Kong AI Gateway · Envoy AI Gateway · Helicone AI Gateway · TensorZero | `systems/*.yaml` + `gateways/*` | next |
| DeepSeek Harness + dsh-llm-fallbacks · Vercel AI SDK · LangChain `with_fallbacks` · Spring AI · LangChain4j | adapters | next |

Hosted-only gateways (OpenRouter, Vercel AI Gateway cloud, Portkey cloud) cannot be pointed at a fake provider and are out of scope.

## The scenarios

| ID | Fault the wall injects | What a correct system does |
|---|---|---|
| S01 | 429 with `Retry-After: 2`, once | Honour the header; retry after ~2 s |
| S02 | 429 without Retry-After, persistent | Back off with jitter, fail over; never hammer |
| S03 | 500 once, then healthy | Retry the same provider once |
| S04 | 503 persistent | Fail over within the retry budget |
| S05 | TCP reset before headers, once | Retry or fail over; answer |
| S06 | No response at all | Time out well before the provider gives up; fail over |
| S07 | First token after 20 s | Answer; a time-to-first-token limit is noted |
| S08 | Stream cut after 40 of 60 tokens | Fail over to the whole answer, or a clear error; never a "successful" truncated answer |
| S09 | Stream stalls 30 s, connection open | Detect the stall; stay healthy afterwards |
| S10 | Malformed chunk mid-stream | Skip it or fail cleanly; nothing partial leaks |
| S11 | Stream ends without `[DONE]` | Finalise promptly; report usage |
| S12 | 400 `context_length_exceeded` | No retry on the same model; route to a larger one |
| S13 | 400 content-filter rejection | No retry; propagate the reason |
| S14 | Cut stream, and the fallback rejects assistant prefill | Capability-aware continuation, or a clean restart; never mask the real error with the prefill 400 |
| S15 | Primary down 60 s, then healthy; twenty requests | Serve from the fallback; probe; return to the primary |
| S16 | Primary 503; fallback answers | Report the fallback's model and usage; don't bill the failed attempts |

Full definitions, including the machine checks each scenario scores, are in [`scenarios/catalogue.yaml`](scenarios/catalogue.yaml).

## How a cell is scored

Each cell is one scenario through one system.

- **pass** — the caller got the complete answer (or, for S13, the correct error) and every conduct check passed.
- **partial** — rescued, but an advisory check failed (didn't honour Retry-After, no usage block, no time-to-first-token limit).
- **safe** — not rescued, but a bounded, clean error with every required check passed. A system with no fallback can do no better than this on most scenarios.
- **fail** — a hang, a truncated answer presented as success, or a required conduct check failed (hammering, retrying a 400, masking the real error, dying after a malformed chunk).

Conduct checks come from the wall's log: how many attempts, how far apart, whether the system was still alive afterwards. The runner never reads a system's internals.

## Referee conduct

Vendors receive each failing scenario as an issue with a one-command reproduction and **seven days' notice** before a scorecard names them. Methodology is versioned; raw logs ship with every scorecard; scenario pull requests from vendors are welcome; every fix is credited in the changelog. The score is the score.

## Add a system

Copy a file in `systems/`, point it at an adapter (`direct`, `endpoint`, `reference`, `openai-python`, `litellm-router`) and set its `capabilities`. For any OpenAI-compatible gateway, `endpoint` works as is: configure the gateway so that each scenario's model name routes to the wall with `fb-ok` as fallback (`python -m failoverbench litellm-config` writes that config for LiteLLM). For an SDK or framework, add an adapter under `failoverbench/adapters/` — the interface is one `complete()` method.

## Licence

Harness: MIT. Results (`results/`): CC BY 4.0.
