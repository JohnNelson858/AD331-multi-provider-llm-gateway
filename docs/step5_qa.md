# Step 5 QA report

Student: John Nelson · AD 331 · Local date: October 25, 2026

## Observed result

`uv run pytest -q`: **54 passed, 2 skipped**. All 56 cases were collected.
`node tests/web_client_smoke.cjs`: passed (simulated DOM and transport).
`git diff --check`: passed for this change.

No paid API calls or real credentials were used. Provider requests are mocked
in the default suite. Unlike Step 2, the gateway tests now execute real tiktoken;
the first run may download its vocabulary data. A vocabulary download is not a
paid inference request. Do not describe these results as live integration success.

## Assignment coverage

| Requirement | Evidence | Status |
| --- | --- | --- |
| Unified typed streams from both providers | `tests/test_gateway.py`: concatenated text, valid StreamChunk events, provider usage tails | Passed with mocked providers |
| Fifty-word token-count validation | Fixed 50-word prompt has 150 o200k_base tokens; real gateway tokenizer equals the independently selected reference encoding exactly | Passed locally |
| Final telemetry sanity | Both nonempty provider fixtures have positive cost, TTFT and tokens/sec; controlled-clock TTFT ignores empty metadata | Passed with mocked providers |
| Missing/malformed credentials | Both providers tested against absent, blank, placeholder, short, whitespace and newline-containing values; no SDK client is constructed | Passed |
| Secret redaction | Both SDKs' authentication, rate-limit and connection errors contain fake secrets; domain error strings, repr, implicit chains and captured gateway logs are checked | Passed for tested paths |
| Billing arithmetic | Decimal precision, independent cached-read/write calculations, invalid totals and unsupported writes | Passed |
| Async lifetime/concurrency | Cancellation, abandoned generators, concurrent isolated counters, pooled client reuse and shutdown regressions | Passed with mocked streams |
| Web boundary | SSE, Decimal display, input validation, static errors, host/origin checks | Passed via TestClient |
| Browser controls | Client smoke script checks partial display, split UTF-8, final metrics, provider switch, Stop, recovery | Passed in a simulated DOM |
| Actual browser appearance | John's screenshot and confirmation after Step 4 | Desktop page visually confirmed; live interactions unverified |
| Real provider stream/usage | Two opt-in tests in `tests/test_live.py` | Skipped; local keys/account access needed |

## Token-count interpretation

The deterministic prompt is `microcontroller01` through `microcontroller50`,
separated by single spaces. It has exactly 50 whitespace-separated words and
150 o200k_base tokens. Test input is fixed and reproducible.

The local test measures the raw text against the actual tiktoken encoding;
it matches exactly, exceeding the assignment's ±10% local tolerance. A deliberately
different mocked billed count verifies that provider usage replaces estimates.
That fixture is **not evidence** that real billed usage matches the tokenizer.

Chat framing can add input tokens that plain-text encoding does not count.
The paid OpenAI test measures the real billed-vs-local difference against ±10%
for this prompt. A mismatch must be investigated; do not adjust counters to make
the test pass. Anthropic uses a different tokenizer, so OpenAI's tiktoken
reference is not applied to Anthropic. Its paid test checks provider totals and
telemetry instead.

References: [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting)
and [official tiktoken](https://github.com/openai/tiktoken).

## New defect found and fixed

Whitespace-containing keys reached SDK construction. Four regression cases
(two malformed values × two providers) failed before the fix, with 16 other
security cases passing. Internal spaces/newlines could produce a generic
provider failure rather than the required descriptive AuthenticationError.

Before, in `src/gateway.py`:

```python
if not key or not key.startswith("sk-") or len(key) < 20 or "your_" in key:
    raise AuthenticationError(f"Set a valid {name} in your local environment.")
```

After:

```python
if (not key or not key.startswith("sk-") or len(key) < 20 or "your_" in key.lower()
        or any(ch.isspace() or not ch.isascii() or ord(ch) < 33 or ord(ch) == 127 for ch in key)):
    raise AuthenticationError(f"Set a valid {name} in your local environment.")
```

Outer whitespace is trimmed. Internal whitespace, non-ASCII characters and
control characters are rejected before SDK construction. Local checks validate
key shape, not whether a provider accepts the key. Rejected server credentials
still map to a sanitized AuthenticationError.

## Running on the Dell

Stop the running Uvicorn server with Ctrl+C, then run from the repository folder:

```powershell
git pull --ff-only
uv run pytest -v
```

Expected default outcome: **54 passed, 2 skipped**. If tokenizer data is not
cached, allow its first-use download to finish. A download error is a failed
check, not permission to substitute a stub or silently skip validation.

Optional client smoke test, only if Node.js is installed:

```powershell
node tests/web_client_smoke.cjs
```

## Paid live checks — separate, not executed

These commands create real API usage. First configure local `.env` credentials,
confirm billing/model access, and review the configured model IDs/rates. Do not
paste keys into chat, prompts, screenshots or the public repository.

Each selected case makes one inference request capped at 32 output tokens;
input tokens are also billable. Existing SDK retries remain disabled. Missing
keys fail live tests rather than being silently skipped after explicit opt-in.

```powershell
# OpenAI only (one paid request)
uv run pytest tests/test_live.py --live -v -k gpt

# Anthropic only (one paid request)
uv run pytest tests/test_live.py --live -v -k claude
```

The default `pytest` invocation never opts in, even if `.env` already has keys.
The OpenAI example model is marked deprecated in the existing configuration;
verify current account availability before requesting it. Anthropic's legacy
model temperature compatibility is still not live-verified. Do not infer model
availability from passing mocks.

Remaining limits: real provider errors/logging, network cancellation behavior,
mobile layout in a native browser, one-hour cache pricing, deployed behavior
and the required live video demo remain unverified. Tested sanitized error
paths do not guarantee third-party debug logs or monitoring that captures frame
locals are safe. Step 6 deployment has not started.
