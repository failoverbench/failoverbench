"""Failover Bench — a public crash-test lab for LLM gateways and SDKs.

Three parts:

* ``wall``    — the fake OpenAI-compatible provider that breaks on purpose.
* ``runner``  — pushes a system under test through every scenario and scores it.
* ``report``  — renders the monthly scorecard from the JSON results.
"""

__version__ = "0.1.0"

# The canonical answer every healthy completion returns. Sixty words, so a
# stream cut after forty tokens is detectable and a "successful" truncated
# answer can never pass the completeness check.
CANONICAL_ANSWER = (
    "A gateway earns trust only when the provider behind it misbehaves. "
    "Rate limits arrive without warning, streams die halfway through a sentence, "
    "servers answer with malformed bytes, and a healthy model returns to service "
    "while the breaker is still open. This answer contains exactly sixty words so "
    "that a truncated response can never be mistaken for a complete one again."
)

assert len(CANONICAL_ANSWER.split()) == 60, len(CANONICAL_ANSWER.split())
