# Failover Bench scorecard — 2026-09-07

Profile **full** · methodology v0.1 · failoverbench 0.1.0 · 5 system(s) · 16 scenario(s)

Every cell is one scenario run through one system against the same misbehaving provider. **pass** = the caller got the complete answer and the system behaved; **partial** = rescued, with an advisory conduct issue; **safe** = not rescued, but a bounded, clean error; **fail** = a hang, a truncated answer presented as success, or a conduct check failed. `Np/Mf` = attempts the provider saw on the primary / fallback model; `gap` = seconds between the first two primary attempts.

| Scenario | No gateway (direct, no retries) | LiteLLM proxy (Docker) | LiteLLM Router (in-process) | openai-python SDK (built-in retries) | Reference client (httpx) |
|---|---|---|---|---|---|
| **S01** 429 with Retry-After | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 2.5s · 3.6s</sub> | ✅ pass<br><sub>2p/0f · gap 2.7s · 4.0s</sub> | ✅ pass<br><sub>2p/0f · gap 2.0s · 3.3s</sub> | ✅ pass<br><sub>2p/0f · gap 2.0s · 3.0s</sub> |
| **S02** 429 without Retry-After, persistent | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 0.7s · 5.6s</sub> | ✅ pass<br><sub>3p/1f · gap 0.6s · 5.3s</sub> | ○ safe<br><sub>3p/0f · gap 0.5s · 1.4s</sub> | ✅ pass<br><sub>3p/1f · gap 0.5s · 2.4s</sub> |
| **S03** 500 once, then healthy | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 1.1s · 2.1s</sub> | ✅ pass<br><sub>2p/0f · gap 0.7s · 1.7s</sub> | ✅ pass<br><sub>2p/0f · gap 0.5s · 1.5s</sub> | ✅ pass<br><sub>2p/0f · gap 0.5s · 1.5s</sub> |
| **S04** 503 persistent | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 0.8s · 5.1s</sub> | ✅ pass<br><sub>3p/1f · gap 0.9s · 5.8s</sub> | ○ safe<br><sub>3p/0f · gap 0.5s · 1.4s</sub> | ✅ pass<br><sub>3p/1f · gap 0.4s · 2.2s</sub> |
| **S05** TCP reset before headers | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 1.2s · 2.1s</sub> | ✅ pass<br><sub>2p/0f · gap 0.8s · 1.8s</sub> | ✅ pass<br><sub>2p/0f · gap 0.4s · 1.4s</sub> | ✅ pass<br><sub>2p/0f · gap 0.5s · 1.5s</sub> |
| **S06** No response at all | ○ safe<br><sub>1p/0f · 30.0s</sub> | ❌ fail<br><sub>3p/1f · gap 31.1s · 95.5s</sub> | ❌ fail<br><sub>3p/1f · gap 30.9s · 96.3s</sub> | ❌ fail<br><sub>3p/0f · gap 30.5s · 91.4s</sub> | ✅ pass<br><sub>1p/1f · 11.0s</sub> |
| **S07** Slow first token | ✅ pass<br><sub>1p/0f · 21.0s</sub> | ◐ partial<br><sub>1p/0f · 21.0s</sub> | ◐ partial<br><sub>1p/0f · 21.0s</sub> | ✅ pass<br><sub>1p/0f · 21.0s</sub> | ✅ pass<br><sub>1p/1f · 11.0s</sub> |
| **S08** Stream cut mid-answer | ○ safe<br><sub>1p/0f · 0.6s</sub> | ❌ fail<br><sub>1p/0f · 0.7s · TRUNCATED</sub> | ○ safe<br><sub>1p/0f · 0.7s</sub> | ○ safe<br><sub>1p/0f · 0.6s</sub> | ✅ pass<br><sub>3p/1f · gap 1.2s · 4.3s</sub> |
| **S09** Stream stalls | ○ safe<br><sub>1p/0f · 30.3s</sub> | ❌ fail<br><sub>1p/0f · 30.3s · TRUNCATED</sub> | ○ safe<br><sub>1p/0f · 30.3s</sub> | ○ safe<br><sub>1p/0f · 30.3s</sub> | ✅ pass<br><sub>1p/1f · 11.3s</sub> |
| **S10** Malformed chunk in the stream | ✅ pass<br><sub>1p/0f · 1.0s</sub> | ❌ fail<br><sub>1p/0f · 0.2s · TRUNCATED</sub> | ○ safe<br><sub>1p/0f · 0.2s</sub> | ○ safe<br><sub>1p/0f · 0.2s</sub> | ✅ pass<br><sub>1p/0f · 1.0s</sub> |
| **S11** Stream ends without [DONE] | ✅ pass<br><sub>1p/0f · 1.0s</sub> | ✅ pass<br><sub>1p/0f · 1.0s</sub> | ✅ pass<br><sub>1p/0f · 1.0s</sub> | ✅ pass<br><sub>1p/0f · 1.0s</sub> | ✅ pass<br><sub>1p/0f · 1.0s</sub> |
| **S12** Context length exceeded | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>1p/1f · 1.0s</sub> | ✅ pass<br><sub>1p/1f · 1.0s</sub> | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>1p/1f · 1.0s</sub> |
| **S13** Content-filter rejection | ✅ pass<br><sub>1p/0f · 0.0s</sub> | ◐ partial<br><sub>1p/1f · 1.0s</sub> | ◐ partial<br><sub>1p/1f · 1.0s</sub> | ✅ pass<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>1p/0f · 0.0s</sub> |
| **S14** Fallback target rejects prefill | ○ safe<br><sub>1p/0f · 0.6s</sub> | ❌ fail<br><sub>1p/0f · 0.7s · TRUNCATED</sub> | ○ safe<br><sub>1p/0f · 0.7s</sub> | ○ safe<br><sub>1p/0f · 0.6s</sub> | ✅ pass<br><sub>3p/1f · gap 1.2s · 4.6s</sub> |
| **S15** Primary flaps: down, then healthy | ○ safe<br><sub>0/15 served in outage · back on primary +0s</sub> | ✅ pass<br><sub>11/11 served in outage · back on primary +0s</sub> | ✅ pass<br><sub>11/11 served in outage · back on primary +2s</sub> | ○ safe<br><sub>0/15 served in outage · back on primary +0s</sub> | ✅ pass<br><sub>15/15 served in outage · back on primary +0s</sub> |
| **S16** Fail-over accounting | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 1.1s · 5.8s</sub> | ✅ pass<br><sub>3p/1f · gap 0.9s · 5.7s</sub> | ○ safe<br><sub>3p/0f · gap 0.4s · 1.3s</sub> | ✅ pass<br><sub>3p/1f · gap 0.6s · 2.7s</sub> |

| System | pass | partial | safe | fail | run time |
|---|---:|---:|---:|---:|---:|
| No gateway (direct, no retries) | 4 | 0 | 12 | 0 | 162s |
| LiteLLM proxy (Docker) | 9 | 2 | 0 | 5 | 253s |
| LiteLLM Router (in-process) | 9 | 2 | 4 | 1 | 254s |
| openai-python SDK (built-in retries) | 6 | 0 | 9 | 1 | 232s |
| Reference client (httpx) | 16 | 0 | 0 | 0 | 136s |

## Check-level detail

### No gateway (direct, no retries)
adapter `direct` · capabilities: fallback=no, streaming=yes · params: `{"read_timeout_s": 30}`

Control row: one request straight at the provider with no retries, no fallback, a 30 s read timeout. What an app gets with zero protection.

**S01 429 with Retry-After** — ○ safe — not rescued — clean error: HTTP 429: Rate limit reached for fb-s01-429-retry-after. Please retry after 2 se
- `retried` FAIL (advisory): 1 primary attempt(s)
- `retry_after_honoured` FAIL (advisory): no second attempt
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.00s fb-s01-429-retry-after #1 -> 429 retry-after=2

**S02 429 without Retry-After, persistent** — ○ safe — not rescued — clean error: HTTP 429: Rate limit reached for fb-s02-429-persistent.
- `no_hammer` pass: 1 attempt(s) in first 3s
- `bounded_attempts` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- wall log: 0.00s fb-s02-429-persistent #1 -> 429

**S03 500 once, then healthy** — ○ safe — not rescued — clean error: HTTP 500: The server had an error while processing your request.
- `no_hang` pass: ended in 0.0s (error)
- `same_provider_retry` FAIL (advisory): 1 primary attempt(s)
- wall log: 0.00s fb-s03-500-then-200 #1 -> 500

**S04 503 persistent** — ○ safe — not rescued — clean error: HTTP 503: The engine is currently overloaded. Please try again later.
- `bounded_attempts` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- wall log: 0.00s fb-s04-503-persistent #1 -> 503

**S05 TCP reset before headers** — ○ safe — not rescued — clean error: ReadError: 
- `no_hang` pass: ended in 0.0s (error)
- wall log: 0.00s fb-s05-reset #1 -> tcp-reset

**S06 No response at all** — ○ safe — not rescued — clean error: ReadTimeout: 
- `bounded` pass: 30.0s
- `no_hang` pass: ended in 30.0s (error)
- wall log: 0.00s fb-s06-no-response #1 -> no-response 120s

**S07 Slow first token** — ✅ pass — rescued
- `no_hang` pass: ended in 21.0s (success)
- `ttft_limit` n/a: n/a — system declares no fallback
- wall log: 0.00s fb-s07-slow-ttft #1 -> 200 stream, first token after 20s

**S08 Stream cut mid-answer** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `no_truncated_success` pass: no success claimed (error)
- `no_hang` pass: ended in 0.6s (error)
- wall log: 0.00s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S09 Stream stalls** — ○ safe — not rescued — clean error: ReadTimeout: 
- `bounded` pass: 30.3s
- `no_truncated_success` pass: no success claimed (error)
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 30.3s (error)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 30s then close

**S10 Malformed chunk in the stream** — ✅ pass — rescued
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: complete answer
- `no_hang` pass: ended in 1.0s (success)
- `recovered_in_place` pass: complete answer
- wall log: 0.00s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 1.0s
- `usage_reported` pass: usage = {'prompt_tokens': 21, 'completion_tokens': 60, 'total_tokens': 81}
- wall log: 0.00s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ○ safe — not rescued — clean error: HTTP 400: This model's maximum context length is 8192 tokens. However, your mess
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- wall log: 0.00s fb-s12-context-length #1 -> 400 context_length_exceeded

**S13 Content-filter rejection** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- `fallback_attempted` info: 0 fallback attempt(s)
- wall log: 0.00s fb-s13-content-filter #1 -> 400 content_policy_violation

**S14 Fallback target rejects prefill** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome error
- `no_truncated_success` pass: no success claimed (error)
- wall log: 0.00s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S15 Primary flaps: down, then healthy** — ○ safe — not rescued — clean error: HTTP 503: The engine is currently overloaded. Please try again later.
- `no_hang` pass: 0 hung request(s) of 20
- `served_during_outage` n/a: n/a — system declares no fallback
- `recovered` n/a: n/a — system declares no fallback
- `probe_discipline` pass: 15 primary attempt(s) for 15 request(s) during the outage
- wall log: 0.00s fb-s15-flap #1 -> 503 (down window); 4.00s fb-s15-flap #2 -> 503 (down window); 8.00s fb-s15-flap #3 -> 503 (down window); 12.00s fb-s15-flap #4 -> 503 (down window); 16.00s fb-s15-flap #5 -> 503 (down window); 20.00s fb-s15-flap #6 -> 503 (down window); 24.00s fb-s15-flap #7 -> 503 (down window); 28.00s fb-s15-flap #8 -> 503 (down window); 32.00s fb-s15-flap #9 -> 503 (down window); 36.00s fb-s15-flap #10 -> 503 (down window); 40.00s fb-s15-flap #11 -> 503 (down window); 44.00s fb-s15-flap #12 -> 503 (down window) … (+8 more)

**S16 Fail-over accounting** — ○ safe — not rescued — clean error: HTTP 503: The engine is currently overloaded. Please try again later.
- `reports_fallback_model` n/a: n/a — system declares no fallback
- `usage_present` n/a: n/a — system declares no fallback
- `bounded_attempts` pass: 1 primary attempt(s)
- wall log: 0.00s fb-s16-503-persistent #1 -> 503

### LiteLLM proxy (Docker)
adapter `endpoint` · capabilities: fallback=yes, streaming=yes · params: `{"base_url": "http://127.0.0.1:4000/v1", "api_key": "sk-failoverbench"}`

LiteLLM proxy container configured by `python -m failoverbench litellm-config` (see gateways/litellm). The proxy owns retries and fallbacks.

**S01 429 with Retry-After** — ✅ pass — rescued
- `retried` pass: 2 primary attempt(s)
- `retry_after_honoured` pass: gap 2.54s
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.08s fb-s01-429-retry-after #1 -> 429 retry-after=2; 2.62s fb-s01-429-retry-after #2 -> 200 stream

**S02 429 without Retry-After, persistent** — ✅ pass — rescued
- `no_hammer` pass: 3 attempt(s) in first 3s
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 5.6s (success)
- wall log: 0.01s fb-s02-429-persistent #1 -> 429; 0.67s fb-s02-429-persistent #2 -> 429; 2.00s fb-s02-429-persistent #3 -> 429; 4.58s fb-ok #1 -> 200 stream

**S03 500 once, then healthy** — ✅ pass — rescued
- `no_hang` pass: ended in 2.1s (success)
- `same_provider_retry` pass: 2 primary attempt(s)
- wall log: 0.01s fb-s03-500-then-200 #1 -> 500; 1.09s fb-s03-500-then-200 #2 -> 200 stream

**S04 503 persistent** — ✅ pass — rescued
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 5.1s (success)
- wall log: 0.01s fb-s04-503-persistent #1 -> 503; 0.85s fb-s04-503-persistent #2 -> 503; 1.92s fb-s04-503-persistent #3 -> 503; 4.09s fb-ok #1 -> 200 stream

**S05 TCP reset before headers** — ✅ pass — rescued
- `no_hang` pass: ended in 2.1s (success)
- wall log: 0.01s fb-s05-reset #1 -> tcp-reset; 1.16s fb-s05-reset #2 -> 200 stream

**S06 No response at all** — ❌ fail — failed: bounded
- `bounded` FAIL: 95.5s
- `no_hang` pass: ended in 95.5s (success)
- wall log: 0.01s fb-s06-no-response #1 -> no-response 120s; 31.16s fb-s06-no-response #2 -> no-response 120s; 62.29s fb-s06-no-response #3 -> no-response 120s; 94.53s fb-ok #1 -> 200 stream

**S07 Slow first token** — ◐ partial — rescued; advisory: ttft_limit
- `no_hang` pass: ended in 21.0s (success)
- `ttft_limit` FAIL (advisory): 21.0s
- wall log: 0.01s fb-s07-slow-ttft #1 -> 200 stream, first token after 20s

**S08 Stream cut mid-answer** — ❌ fail — truncated answer presented as success
- `no_truncated_success` FAIL: success with 40/60 words
- `no_hang` pass: ended in 0.7s (success)
- wall log: 0.01s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S09 Stream stalls** — ❌ fail — truncated answer presented as success
- `bounded` pass: 30.3s
- `no_truncated_success` FAIL: success with 20/60 words
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 30.3s (success)
- wall log: 0.01s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 30s then close

**S10 Malformed chunk in the stream** — ❌ fail — truncated answer presented as success
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` FAIL: success with 10/60 words
- `no_hang` pass: ended in 0.2s (success)
- `recovered_in_place` FAIL (advisory): truncated/altered answer
- wall log: 0.01s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 1.0s
- `usage_reported` pass: usage = {'completion_tokens': 60, 'prompt_tokens': 21, 'total_tokens': 81, 'completion_tokens_details': {'reasoning_tokens': 0}}
- wall log: 0.01s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 1.0s (success)
- wall log: 0.01s fb-s12-context-length #1 -> 400 context_length_exceeded; 0.02s fb-ok #1 -> 200 stream

**S13 Content-filter rejection** — ◐ partial — answered by routing around the rejection
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 1.0s (success)
- `fallback_attempted` pass: 1 fallback attempt(s)
- wall log: 0.01s fb-s13-content-filter #1 -> 400 content_policy_violation; 0.02s fb-ok #1 -> 200 stream

**S14 Fallback target rejects prefill** — ❌ fail — truncated answer presented as success
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome success
- `no_truncated_success` FAIL: success with 40/60 words
- wall log: 0.01s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S15 Primary flaps: down, then healthy** — ✅ pass — rescued
- `no_hang` pass: 0 hung request(s) of 20
- `served_during_outage` pass: 11/11 requests answered while primary was down
- `recovered` pass: primary answered again +0.5s after recovery
- `probe_discipline` info: 31 primary attempt(s) for 11 request(s) during the outage
- wall log: 0.01s fb-s15-flap #1 -> 503 (down window); 1.01s fb-s15-flap #2 -> 503 (down window); 2.64s fb-s15-flap #3 -> 503 (down window); 5.25s fb-ok #1 -> 200 stream; 6.24s fb-s15-flap #4 -> 503 (down window); 7.28s fb-s15-flap #5 -> 503 (down window); 9.05s fb-s15-flap #6 -> 503 (down window); 11.36s fb-ok #2 -> 200 stream; 12.34s fb-s15-flap #7 -> 503 (down window); 13.41s fb-s15-flap #8 -> 503 (down window); 14.78s fb-s15-flap #9 -> 503 (down window); 17.03s fb-ok #3 -> 200 stream … (+39 more)

**S16 Fail-over accounting** — ✅ pass — rescued
- `reports_fallback_model` pass: response.model = 'fb-ok'
- `usage_present` pass: usage = {'completion_tokens': 60, 'prompt_tokens': 21, 'total_tokens': 81, 'completion_tokens_details': {'reasoning_tokens': 0}}
- `bounded_attempts` pass: 3 primary attempt(s)
- wall log: 0.01s fb-s16-503-persistent #1 -> 503; 1.07s fb-s16-503-persistent #2 -> 503; 2.53s fb-s16-503-persistent #3 -> 503; 4.82s fb-ok #1 -> 200 stream

### LiteLLM Router (in-process)
adapter `litellm-router` · capabilities: fallback=yes, streaming=yes · params: `{"num_retries": 2, "timeout_s": 30, "context_window_fallbacks": true}`

litellm.Router with one primary and one fallback deployment per scenario, num_retries=2, timeout=30 s, context_window_fallbacks on. Defaults otherwise.

**S01 429 with Retry-After** — ✅ pass — rescued
- `retried` pass: 2 primary attempt(s)
- `retry_after_honoured` pass: gap 2.74s
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.31s fb-s01-429-retry-after #1 -> 429 retry-after=2; 3.05s fb-s01-429-retry-after #2 -> 200 stream

**S02 429 without Retry-After, persistent** — ✅ pass — rescued
- `no_hammer` pass: 3 attempt(s) in first 3s
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 5.3s (success)
- wall log: 0.01s fb-s02-429-persistent #1 -> 429; 0.63s fb-s02-429-persistent #2 -> 429; 2.08s fb-s02-429-persistent #3 -> 429; 4.30s fb-ok #1 -> 200 stream

**S03 500 once, then healthy** — ✅ pass — rescued
- `no_hang` pass: ended in 1.7s (success)
- `same_provider_retry` pass: 2 primary attempt(s)
- wall log: 0.01s fb-s03-500-then-200 #1 -> 500; 0.69s fb-s03-500-then-200 #2 -> 200 stream

**S04 503 persistent** — ✅ pass — rescued
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 5.8s (success)
- wall log: 0.01s fb-s04-503-persistent #1 -> 503; 0.88s fb-s04-503-persistent #2 -> 503; 2.38s fb-s04-503-persistent #3 -> 503; 4.80s fb-ok #1 -> 200 stream

**S05 TCP reset before headers** — ✅ pass — rescued
- `no_hang` pass: ended in 1.8s (success)
- wall log: 0.01s fb-s05-reset #1 -> tcp-reset; 0.79s fb-s05-reset #2 -> 200 stream

**S06 No response at all** — ❌ fail — failed: bounded
- `bounded` FAIL: 96.3s
- `no_hang` pass: ended in 96.3s (success)
- wall log: 0.01s fb-s06-no-response #1 -> no-response 120s; 30.91s fb-s06-no-response #2 -> no-response 120s; 62.68s fb-s06-no-response #3 -> no-response 120s; 95.31s fb-ok #1 -> 200 stream

**S07 Slow first token** — ◐ partial — rescued; advisory: ttft_limit
- `no_hang` pass: ended in 21.0s (success)
- `ttft_limit` FAIL (advisory): 21.0s
- wall log: 0.01s fb-s07-slow-ttft #1 -> 200 stream, first token after 20s

**S08 Stream cut mid-answer** — ○ safe — not rescued — clean error: APIConnectionError: litellm.APIConnectionError: APIConnectionError: OpenAIExcept
- `no_truncated_success` pass: no success claimed (error)
- `no_hang` pass: ended in 0.7s (error)
- wall log: 0.01s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S09 Stream stalls** — ○ safe — not rescued — clean error: APIConnectionError: litellm.APIConnectionError: APIConnectionError: OpenAIExcept
- `bounded` pass: 30.3s
- `no_truncated_success` pass: no success claimed (error)
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 30.3s (error)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 30s then close

**S10 Malformed chunk in the stream** — ○ safe — not rescued — clean error: APIConnectionError: litellm.APIConnectionError: APIConnectionError: OpenAIExcept
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: no success claimed (error)
- `no_hang` pass: ended in 0.2s (error)
- `recovered_in_place` FAIL (advisory): error
- wall log: 0.01s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 1.0s
- `usage_reported` pass: usage = {'completion_tokens': 60, 'prompt_tokens': 21, 'total_tokens': 81, 'completion_tokens_details': {'accepted_prediction_tokens': None, 'audio_tokens': None, 'reasoning_tokens': 0, 'rejected_prediction_tokens': None, 'text_tokens': None, 'image_tokens': None, 'video_tokens': None}, 'prompt_tokens_details': None}
- wall log: 0.01s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 1.0s (success)
- wall log: 0.01s fb-s12-context-length #1 -> 400 context_length_exceeded; 0.02s fb-ok #1 -> 200 stream

**S13 Content-filter rejection** — ◐ partial — answered by routing around the rejection
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 1.0s (success)
- `fallback_attempted` pass: 1 fallback attempt(s)
- wall log: 0.01s fb-s13-content-filter #1 -> 400 content_policy_violation; 0.02s fb-ok #1 -> 200 stream

**S14 Fallback target rejects prefill** — ○ safe — not rescued — clean error: APIConnectionError: litellm.APIConnectionError: APIConnectionError: OpenAIExcept
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome error
- `no_truncated_success` pass: no success claimed (error)
- wall log: 0.01s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S15 Primary flaps: down, then healthy** — ✅ pass — rescued
- `no_hang` pass: 0 hung request(s) of 20
- `served_during_outage` pass: 11/11 requests answered while primary was down
- `recovered` pass: primary answered again +2.2s after recovery
- `probe_discipline` info: 33 primary attempt(s) for 11 request(s) during the outage
- wall log: 0.01s fb-s15-flap #1 -> 503 (down window); 0.61s fb-s15-flap #2 -> 503 (down window); 1.77s fb-s15-flap #3 -> 503 (down window); 4.09s fb-ok #1 -> 200 stream; 5.08s fb-s15-flap #4 -> 503 (down window); 6.02s fb-s15-flap #5 -> 503 (down window); 7.65s fb-s15-flap #6 -> 503 (down window); 10.40s fb-ok #2 -> 200 stream; 11.39s fb-s15-flap #7 -> 503 (down window); 12.12s fb-s15-flap #8 -> 503 (down window); 13.61s fb-s15-flap #9 -> 503 (down window); 16.10s fb-ok #3 -> 200 stream … (+41 more)

**S16 Fail-over accounting** — ✅ pass — rescued
- `reports_fallback_model` pass: response.model = 'fb-ok'
- `usage_present` pass: usage = {'completion_tokens': 60, 'prompt_tokens': 21, 'total_tokens': 81, 'completion_tokens_details': {'accepted_prediction_tokens': None, 'audio_tokens': None, 'reasoning_tokens': 0, 'rejected_prediction_tokens': None, 'text_tokens': None, 'image_tokens': None, 'video_tokens': None}, 'prompt_tokens_details': None}
- `bounded_attempts` pass: 3 primary attempt(s)
- wall log: 0.01s fb-s16-503-persistent #1 -> 503; 0.88s fb-s16-503-persistent #2 -> 503; 2.09s fb-s16-503-persistent #3 -> 503; 4.73s fb-ok #1 -> 200 stream

### openai-python SDK (built-in retries)
adapter `openai-python` · capabilities: fallback=no, streaming=yes · params: `{"max_retries": 2, "timeout_s": 30}`

The official SDK with its defaults except timeout (600 s → 30 s so a run stays bounded). No fallback concept, so fail-over checks are n/a.

**S01 429 with Retry-After** — ✅ pass — rescued
- `retried` pass: 2 primary attempt(s)
- `retry_after_honoured` pass: gap 2.01s
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.30s fb-s01-429-retry-after #1 -> 429 retry-after=2; 2.31s fb-s01-429-retry-after #2 -> 200 stream

**S02 429 without Retry-After, persistent** — ○ safe — not rescued — clean error: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for 
- `no_hammer` pass: 3 attempt(s) in first 3s
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 1.4s (error)
- wall log: 0.00s fb-s02-429-persistent #1 -> 429; 0.49s fb-s02-429-persistent #2 -> 429; 1.42s fb-s02-429-persistent #3 -> 429

**S03 500 once, then healthy** — ✅ pass — rescued
- `no_hang` pass: ended in 1.5s (success)
- `same_provider_retry` pass: 2 primary attempt(s)
- wall log: 0.00s fb-s03-500-then-200 #1 -> 500; 0.49s fb-s03-500-then-200 #2 -> 200 stream

**S04 503 persistent** — ○ safe — not rescued — clean error: InternalServerError: Error code: 503 - {'error': {'message': 'The engine is curr
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 1.4s (error)
- wall log: 0.00s fb-s04-503-persistent #1 -> 503; 0.49s fb-s04-503-persistent #2 -> 503; 1.45s fb-s04-503-persistent #3 -> 503

**S05 TCP reset before headers** — ✅ pass — rescued
- `no_hang` pass: ended in 1.4s (success)
- wall log: 0.00s fb-s05-reset #1 -> tcp-reset; 0.40s fb-s05-reset #2 -> 200 stream

**S06 No response at all** — ❌ fail — failed: bounded
- `bounded` FAIL: 91.4s
- `no_hang` pass: ended in 91.4s (error)
- wall log: 0.00s fb-s06-no-response #1 -> no-response 120s; 30.45s fb-s06-no-response #2 -> no-response 120s; 61.41s fb-s06-no-response #3 -> no-response 120s

**S07 Slow first token** — ✅ pass — rescued
- `no_hang` pass: ended in 21.0s (success)
- `ttft_limit` n/a: n/a — system declares no fallback
- wall log: 0.00s fb-s07-slow-ttft #1 -> 200 stream, first token after 20s

**S08 Stream cut mid-answer** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `no_truncated_success` pass: no success claimed (error)
- `no_hang` pass: ended in 0.6s (error)
- wall log: 0.00s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S09 Stream stalls** — ○ safe — not rescued — clean error: ReadTimeout: 
- `bounded` pass: 30.3s
- `no_truncated_success` pass: no success claimed (error)
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 30.3s (error)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 30s then close

**S10 Malformed chunk in the stream** — ○ safe — not rescued — clean error: JSONDecodeError: Expecting value: line 1 column 94 (char 93)
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: no success claimed (error)
- `no_hang` pass: ended in 0.2s (error)
- `recovered_in_place` FAIL (advisory): error
- wall log: 0.00s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 1.0s
- `usage_reported` pass: usage = {'completion_tokens': 60, 'prompt_tokens': 21, 'total_tokens': 81, 'completion_tokens_details': None, 'prompt_tokens_details': None}
- wall log: 0.00s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ○ safe — not rescued — clean error: BadRequestError: Error code: 400 - {'error': {'message': "This model's maximum c
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- wall log: 0.00s fb-s12-context-length #1 -> 400 context_length_exceeded

**S13 Content-filter rejection** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- `fallback_attempted` info: 0 fallback attempt(s)
- wall log: 0.00s fb-s13-content-filter #1 -> 400 content_policy_violation

**S14 Fallback target rejects prefill** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome error
- `no_truncated_success` pass: no success claimed (error)
- wall log: 0.00s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S15 Primary flaps: down, then healthy** — ○ safe — not rescued — clean error: InternalServerError: Error code: 503 - {'error': {'message': 'The engine is curr
- `no_hang` pass: 0 hung request(s) of 20
- `served_during_outage` n/a: n/a — system declares no fallback
- `recovered` n/a: n/a — system declares no fallback
- `probe_discipline` info: 45 primary attempt(s) for 15 request(s) during the outage
- wall log: 0.00s fb-s15-flap #1 -> 503 (down window); 0.41s fb-s15-flap #2 -> 503 (down window); 1.29s fb-s15-flap #3 -> 503 (down window); 4.00s fb-s15-flap #4 -> 503 (down window); 4.46s fb-s15-flap #5 -> 503 (down window); 5.41s fb-s15-flap #6 -> 503 (down window); 8.00s fb-s15-flap #7 -> 503 (down window); 8.45s fb-s15-flap #8 -> 503 (down window); 9.35s fb-s15-flap #9 -> 503 (down window); 12.00s fb-s15-flap #10 -> 503 (down window); 12.49s fb-s15-flap #11 -> 503 (down window); 13.48s fb-s15-flap #12 -> 503 (down window) … (+38 more)

**S16 Fail-over accounting** — ○ safe — not rescued — clean error: InternalServerError: Error code: 503 - {'error': {'message': 'The engine is curr
- `reports_fallback_model` n/a: n/a — system declares no fallback
- `usage_present` n/a: n/a — system declares no fallback
- `bounded_attempts` pass: 3 primary attempt(s)
- wall log: 0.00s fb-s16-503-persistent #1 -> 503; 0.40s fb-s16-503-persistent #2 -> 503; 1.34s fb-s16-503-persistent #3 -> 503

### Reference client (httpx)
adapter `reference` · capabilities: fallback=yes, streaming=yes · params: `{"max_attempts": 3, "base_backoff_s": 0.5, "stall_limit_s": 10, "ttft_limit_s": 10, "connect_timeout_s": 5}`

A small client written to pass: honours Retry-After, backs off with jitter, retries 5xx/resets/cut streams up to 3 times, fails over on timeouts and context-length errors, never retries content-filter 400s, restarts without prefill. It has no circuit breaker, so S15 shows what stateless retrying looks like.

**S01 429 with Retry-After** — ✅ pass — rescued
- `retried` pass: 2 primary attempt(s)
- `retry_after_honoured` pass: gap 2.00s
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.00s fb-s01-429-retry-after #1 -> 429 retry-after=2; 2.00s fb-s01-429-retry-after #2 -> 200 stream

**S02 429 without Retry-After, persistent** — ✅ pass — rescued
- `no_hammer` pass: 3 attempt(s) in first 3s
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 2.4s (success)
- wall log: 0.00s fb-s02-429-persistent #1 -> 429; 0.53s fb-s02-429-persistent #2 -> 429; 1.46s fb-s02-429-persistent #3 -> 429; 1.47s fb-ok #1 -> 200 stream

**S03 500 once, then healthy** — ✅ pass — rescued
- `no_hang` pass: ended in 1.5s (success)
- `same_provider_retry` pass: 2 primary attempt(s)
- wall log: 0.00s fb-s03-500-then-200 #1 -> 500; 0.55s fb-s03-500-then-200 #2 -> 200 stream

**S04 503 persistent** — ✅ pass — rescued
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 2.2s (success)
- wall log: 0.00s fb-s04-503-persistent #1 -> 503; 0.43s fb-s04-503-persistent #2 -> 503; 1.28s fb-s04-503-persistent #3 -> 503; 1.28s fb-ok #1 -> 200 stream

**S05 TCP reset before headers** — ✅ pass — rescued
- `no_hang` pass: ended in 1.5s (success)
- wall log: 0.00s fb-s05-reset #1 -> tcp-reset; 0.54s fb-s05-reset #2 -> 200 stream

**S06 No response at all** — ✅ pass — rescued
- `bounded` pass: 11.0s
- `no_hang` pass: ended in 11.0s (success)
- wall log: 0.00s fb-s06-no-response #1 -> no-response 120s; 10.01s fb-ok #1 -> 200 stream

**S07 Slow first token** — ✅ pass — rescued
- `no_hang` pass: ended in 11.0s (success)
- `ttft_limit` pass: 11.0s
- wall log: 0.00s fb-s07-slow-ttft #1 -> 200 stream, first token after 20s; 10.00s fb-ok #1 -> 200 stream

**S08 Stream cut mid-answer** — ✅ pass — rescued
- `no_truncated_success` pass: complete answer
- `no_hang` pass: ended in 4.3s (success)
- wall log: 0.00s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk); 1.24s fb-s08-stream-cut #2 -> 200 stream cut after 40 tokens (no terminating chunk); 2.70s fb-s08-stream-cut #3 -> 200 stream cut after 40 tokens (no terminating chunk); 3.35s fb-ok #1 -> 200 stream

**S09 Stream stalls** — ✅ pass — rescued
- `bounded` pass: 11.3s
- `no_truncated_success` pass: complete answer
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 11.3s (success)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 30s then close; 10.31s fb-ok #1 -> 200 stream

**S10 Malformed chunk in the stream** — ✅ pass — rescued
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: complete answer
- `no_hang` pass: ended in 1.0s (success)
- `recovered_in_place` pass: complete answer
- wall log: 0.00s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 1.0s
- `usage_reported` pass: usage = {'prompt_tokens': 21, 'completion_tokens': 60, 'total_tokens': 81}
- wall log: 0.00s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 1.0s (success)
- wall log: 0.00s fb-s12-context-length #1 -> 400 context_length_exceeded; 0.00s fb-ok #1 -> 200 stream

**S13 Content-filter rejection** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- `fallback_attempted` info: 0 fallback attempt(s)
- wall log: 0.00s fb-s13-content-filter #1 -> 400 content_policy_violation

**S14 Fallback target rejects prefill** — ✅ pass — rescued
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome success
- `no_truncated_success` pass: complete answer
- wall log: 0.00s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk); 1.23s fb-s14-stream-cut #2 -> 200 stream cut after 40 tokens (no terminating chunk); 3.02s fb-s14-stream-cut #3 -> 200 stream cut after 40 tokens (no terminating chunk); 3.67s fb-ok-noprefill #1 -> 200 stream

**S15 Primary flaps: down, then healthy** — ✅ pass — rescued
- `no_hang` pass: 0 hung request(s) of 20
- `served_during_outage` pass: 15/15 requests answered while primary was down
- `recovered` pass: primary answered again +0.0s after recovery
- `probe_discipline` info: 45 primary attempt(s) for 15 request(s) during the outage
- wall log: 0.00s fb-s15-flap #1 -> 503 (down window); 0.52s fb-s15-flap #2 -> 503 (down window); 1.68s fb-s15-flap #3 -> 503 (down window); 1.69s fb-ok #1 -> 200 stream; 4.00s fb-s15-flap #4 -> 503 (down window); 4.50s fb-s15-flap #5 -> 503 (down window); 5.57s fb-s15-flap #6 -> 503 (down window); 5.58s fb-ok #2 -> 200 stream; 8.00s fb-s15-flap #7 -> 503 (down window); 8.51s fb-s15-flap #8 -> 503 (down window); 9.40s fb-s15-flap #9 -> 503 (down window); 9.40s fb-ok #3 -> 200 stream … (+53 more)

**S16 Fail-over accounting** — ✅ pass — rescued
- `reports_fallback_model` pass: response.model = 'fb-ok'
- `usage_present` pass: usage = {'prompt_tokens': 21, 'completion_tokens': 60, 'total_tokens': 81}
- `bounded_attempts` pass: 3 primary attempt(s)
- wall log: 0.00s fb-s16-503-persistent #1 -> 503; 0.60s fb-s16-503-persistent #2 -> 503; 1.75s fb-s16-503-persistent #3 -> 503; 1.75s fb-ok #1 -> 200 stream

---
Results are published under CC BY 4.0; the harness is MIT. Methodology and raw logs: see the repository.
