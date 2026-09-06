<!-- First run of the harness, fast profile, sandbox, 7 Sep 2026. Not a published scorecard: fast timings, two rows. -->
# Failover Bench scorecard — 2026-09-06

Profile **fast** · methodology v0.1 · failoverbench 0.1.0 · 2 system(s) · 16 scenario(s)

Every cell is one scenario run through one system against the same misbehaving provider. **pass** = the caller got the complete answer and the system behaved; **partial** = rescued, with an advisory conduct issue; **safe** = not rescued, but a bounded, clean error; **fail** = a hang, a truncated answer presented as success, or a conduct check failed. `Np/Mf` = attempts the provider saw on the primary / fallback model; `gap` = seconds between the first two primary attempts.

| Scenario | No gateway (direct, no retries) | Reference client (httpx) |
|---|---|---|
| **S01** 429 with Retry-After | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 2.0s · 2.3s</sub> |
| **S02** 429 without Retry-After, persistent | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 0.6s · 2.0s</sub> |
| **S03** 500 once, then healthy | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 0.6s · 0.9s</sub> |
| **S04** 503 persistent | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 0.5s · 1.7s</sub> |
| **S05** TCP reset before headers | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>2p/0f · gap 0.6s · 0.9s</sub> |
| **S06** No response at all | ○ safe<br><sub>1p/0f · 15.0s</sub> | ✅ pass<br><sub>1p/1f · 10.3s</sub> |
| **S07** Slow first token | ✅ pass<br><sub>1p/0f · 3.3s</sub> | ✅ pass<br><sub>1p/0f · 3.3s</sub> |
| **S08** Stream cut mid-answer | ○ safe<br><sub>1p/0f · 0.2s</sub> | ✅ pass<br><sub>3p/1f · gap 0.6s · 2.5s</sub> |
| **S09** Stream stalls | ○ safe<br><sub>1p/0f · 4.1s</sub> | ✅ pass<br><sub>3p/1f · gap 4.5s · 14.3s</sub> |
| **S10** Malformed chunk in the stream | ✅ pass<br><sub>1p/0f · 0.3s</sub> | ✅ pass<br><sub>1p/0f · 0.3s</sub> |
| **S11** Stream ends without [DONE] | ✅ pass<br><sub>1p/0f · 0.3s</sub> | ✅ pass<br><sub>1p/0f · 0.3s</sub> |
| **S12** Context length exceeded | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>1p/1f · 0.3s</sub> |
| **S13** Content-filter rejection | ✅ pass<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>1p/0f · 0.0s</sub> |
| **S14** Fallback target rejects prefill | ○ safe<br><sub>1p/0f · 0.2s</sub> | ✅ pass<br><sub>3p/1f · gap 0.8s · 2.4s</sub> |
| **S15** Primary flaps: down, then healthy | ○ safe<br><sub>0/5 served in outage · back on primary +0s</sub> | ✅ pass<br><sub>4/4 served in outage · back on primary +0s</sub> |
| **S16** Fail-over accounting | ○ safe<br><sub>1p/0f · 0.0s</sub> | ✅ pass<br><sub>3p/1f · gap 0.5s · 2.0s</sub> |

| System | pass | partial | safe | fail | run time |
|---|---:|---:|---:|---:|---:|
| No gateway (direct, no retries) | 4 | 0 | 12 | 0 | 35s |
| Reference client (httpx) | 16 | 0 | 0 | 0 | 55s |

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

**S06 No response at all** — ○ safe — not rescued — clean error: RemoteProtocolError: Server disconnected without sending a response.
- `bounded` pass: 15.0s
- `no_hang` pass: ended in 15.0s (error)
- wall log: 0.00s fb-s06-no-response #1 -> no-response 15s

**S07 Slow first token** — ✅ pass — rescued
- `no_hang` pass: ended in 3.3s (success)
- `ttft_limit` n/a: n/a — system declares no fallback
- wall log: 0.00s fb-s07-slow-ttft #1 -> 200 stream, first token after 3s

**S08 Stream cut mid-answer** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `no_truncated_success` pass: no success claimed (error)
- `no_hang` pass: ended in 0.2s (error)
- wall log: 0.00s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk)

**S09 Stream stalls** — ○ safe — not rescued — clean error: RemoteProtocolError: peer closed connection without sending complete message bod
- `bounded` pass: 4.1s
- `no_truncated_success` pass: no success claimed (error)
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 4.1s (error)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 4s then close

**S10 Malformed chunk in the stream** — ✅ pass — rescued
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: complete answer
- `no_hang` pass: ended in 0.3s (success)
- `recovered_in_place` pass: complete answer
- wall log: 0.00s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 0.3s
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
- `no_hang` pass: 0 hung request(s) of 10
- `served_during_outage` n/a: n/a — system declares no fallback
- `recovered` n/a: n/a — system declares no fallback
- `probe_discipline` pass: 5 primary attempt(s) for 5 request(s) during the outage
- wall log: 0.00s fb-s15-flap #1 -> 503 (down window); 1.20s fb-s15-flap #2 -> 503 (down window); 2.40s fb-s15-flap #3 -> 503 (down window); 3.60s fb-s15-flap #4 -> 503 (down window); 4.80s fb-s15-flap #5 -> 503 (down window); 6.00s fb-s15-flap #6 -> 200 (recovered); 7.20s fb-s15-flap #7 -> 200 (recovered); 8.40s fb-s15-flap #8 -> 200 (recovered); 9.60s fb-s15-flap #9 -> 200 (recovered); 10.80s fb-s15-flap #10 -> 200 (recovered)

**S16 Fail-over accounting** — ○ safe — not rescued — clean error: HTTP 503: The engine is currently overloaded. Please try again later.
- `reports_fallback_model` n/a: n/a — system declares no fallback
- `usage_present` n/a: n/a — system declares no fallback
- `bounded_attempts` pass: 1 primary attempt(s)
- wall log: 0.00s fb-s16-503-persistent #1 -> 503

### Reference client (httpx)
adapter `reference` · capabilities: fallback=yes, streaming=yes · params: `{"max_attempts": 3, "base_backoff_s": 0.5, "stall_limit_s": 10, "ttft_limit_s": 10, "connect_timeout_s": 5}`

A small client written to pass: honours Retry-After, backs off with jitter, retries 5xx/resets/cut streams up to 3 times, fails over on timeouts and context-length errors, never retries content-filter 400s, restarts without prefill. It has no circuit breaker, so S15 shows what stateless retrying looks like.

**S01 429 with Retry-After** — ✅ pass — rescued
- `retried` pass: 2 primary attempt(s)
- `retry_after_honoured` pass: gap 2.00s
- `no_hammer` pass: 1 attempt(s) in first 1.5s
- wall log: 0.00s fb-s01-429-retry-after #1 -> 429 retry-after=2; 2.01s fb-s01-429-retry-after #2 -> 200 stream

**S02 429 without Retry-After, persistent** — ✅ pass — rescued
- `no_hammer` pass: 3 attempt(s) in first 3s
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 2.0s (success)
- wall log: 0.00s fb-s02-429-persistent #1 -> 429; 0.58s fb-s02-429-persistent #2 -> 429; 1.71s fb-s02-429-persistent #3 -> 429; 1.71s fb-ok #1 -> 200 stream

**S03 500 once, then healthy** — ✅ pass — rescued
- `no_hang` pass: ended in 0.9s (success)
- `same_provider_retry` pass: 2 primary attempt(s)
- wall log: 0.00s fb-s03-500-then-200 #1 -> 500; 0.57s fb-s03-500-then-200 #2 -> 200 stream

**S04 503 persistent** — ✅ pass — rescued
- `bounded_attempts` pass: 3 primary attempt(s)
- `no_hang` pass: ended in 1.7s (success)
- wall log: 0.00s fb-s04-503-persistent #1 -> 503; 0.46s fb-s04-503-persistent #2 -> 503; 1.36s fb-s04-503-persistent #3 -> 503; 1.37s fb-ok #1 -> 200 stream

**S05 TCP reset before headers** — ✅ pass — rescued
- `no_hang` pass: ended in 0.9s (success)
- wall log: 0.00s fb-s05-reset #1 -> tcp-reset; 0.58s fb-s05-reset #2 -> 200 stream

**S06 No response at all** — ✅ pass — rescued
- `bounded` pass: 10.3s
- `no_hang` pass: ended in 10.3s (success)
- wall log: 0.00s fb-s06-no-response #1 -> no-response 15s; 10.01s fb-ok #1 -> 200 stream

**S07 Slow first token** — ✅ pass — rescued
- `no_hang` pass: ended in 3.3s (success)
- `ttft_limit` pass: 3.3s
- wall log: 0.00s fb-s07-slow-ttft #1 -> 200 stream, first token after 3s

**S08 Stream cut mid-answer** — ✅ pass — rescued
- `no_truncated_success` pass: complete answer
- `no_hang` pass: ended in 2.5s (success)
- wall log: 0.00s fb-s08-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk); 0.64s fb-s08-stream-cut #2 -> 200 stream cut after 40 tokens (no terminating chunk); 1.96s fb-s08-stream-cut #3 -> 200 stream cut after 40 tokens (no terminating chunk); 2.17s fb-ok #1 -> 200 stream

**S09 Stream stalls** — ✅ pass — rescued
- `bounded` pass: 14.3s
- `no_truncated_success` pass: complete answer
- `alive_after` pass: healthy call succeeded afterwards
- `no_hang` pass: ended in 14.3s (success)
- wall log: 0.00s fb-s09-stream-stall #1 -> 200 stream stalled after 20 tokens for 4s then close; 4.54s fb-s09-stream-stall #2 -> 200 stream stalled after 20 tokens for 4s then close; 9.85s fb-s09-stream-stall #3 -> 200 stream stalled after 20 tokens for 4s then close; 13.97s fb-ok #1 -> 200 stream

**S10 Malformed chunk in the stream** — ✅ pass — rescued
- `alive_after` pass: healthy call succeeded afterwards
- `no_garbage` pass: complete answer
- `no_hang` pass: ended in 0.3s (success)
- `recovered_in_place` pass: complete answer
- wall log: 0.00s fb-s10-malformed-chunk #1 -> 200 stream with malformed chunk at token 10

**S11 Stream ends without [DONE]** — ✅ pass — rescued
- `prompt_finalise` pass: 0.3s
- `usage_reported` pass: usage = {'prompt_tokens': 21, 'completion_tokens': 60, 'total_tokens': 81}
- wall log: 0.00s fb-s11-no-done #1 -> 200 stream complete, [DONE] omitted

**S12 Context length exceeded** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.3s (success)
- wall log: 0.00s fb-s12-context-length #1 -> 400 context_length_exceeded; 0.00s fb-ok #1 -> 200 stream

**S13 Content-filter rejection** — ✅ pass — rescued
- `no_same_model_retry` pass: 1 primary attempt(s)
- `no_hang` pass: ended in 0.0s (error)
- `fallback_attempted` info: 0 fallback attempt(s)
- wall log: 0.00s fb-s13-content-filter #1 -> 400 content_policy_violation

**S14 Fallback target rejects prefill** — ✅ pass — rescued
- `no_prefill_masking` pass: 0 prefill rejection(s) at the fallback; final outcome success
- `no_truncated_success` pass: complete answer
- wall log: 0.00s fb-s14-stream-cut #1 -> 200 stream cut after 40 tokens (no terminating chunk); 0.77s fb-s14-stream-cut #2 -> 200 stream cut after 40 tokens (no terminating chunk); 1.90s fb-s14-stream-cut #3 -> 200 stream cut after 40 tokens (no terminating chunk); 2.12s fb-ok-noprefill #1 -> 200 stream

**S15 Primary flaps: down, then healthy** — ✅ pass — rescued
- `no_hang` pass: 0 hung request(s) of 10
- `served_during_outage` pass: 4/4 requests answered while primary was down
- `recovered` pass: primary answered again +0.2s after recovery
- `probe_discipline` info: 10 primary attempt(s) for 4 request(s) during the outage
- wall log: 0.00s fb-s15-flap #1 -> 503 (down window); 0.56s fb-s15-flap #2 -> 503 (down window); 1.68s fb-s15-flap #3 -> 503 (down window); 1.68s fb-ok #1 -> 200 stream; 2.00s fb-s15-flap #4 -> 503 (down window); 2.58s fb-s15-flap #5 -> 503 (down window); 3.50s fb-s15-flap #6 -> 503 (down window); 3.50s fb-ok #2 -> 200 stream; 3.82s fb-s15-flap #7 -> 503 (down window); 4.30s fb-s15-flap #8 -> 503 (down window); 5.38s fb-s15-flap #9 -> 503 (down window); 5.38s fb-ok #3 -> 200 stream … (+8 more)

**S16 Fail-over accounting** — ✅ pass — rescued
- `reports_fallback_model` pass: response.model = 'fb-ok'
- `usage_present` pass: usage = {'prompt_tokens': 21, 'completion_tokens': 60, 'total_tokens': 81}
- `bounded_attempts` pass: 3 primary attempt(s)
- wall log: 0.00s fb-s16-503-persistent #1 -> 503; 0.53s fb-s16-503-persistent #2 -> 503; 1.73s fb-s16-503-persistent #3 -> 503; 1.73s fb-ok #1 -> 200 stream

---
Results are published under CC BY 4.0; the harness is MIT. Methodology and raw logs: see the repository.
