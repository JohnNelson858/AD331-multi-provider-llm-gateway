# Step 5 QA report

Student: John Nelson · AD 331 · Updated October 27, 2026

## Final Step 5 result

On October 27, John ran `uv run pytest -v --live` on his Dell. The terminal
screenshot supplied in this conversation shows **57 passed in 18.50s**, with
no failures or skipped tests. Both live provider cases passed, including the
OpenAI fifty-word billed-vs-local token comparison. The screenshot contains the
final summary, not per-request metrics; no unreported live-test measurements
are inferred. The assistant did not execute these paid requests or handle keys.

Both providers also succeeded in John's local web interface. His Anthropic
screenshot shows FINAL usage: 17 input tokens, 33 output tokens, TTFT 706.7 ms,
32.9 tokens/sec displayed, $0.000182 calculated cost, and normal `end_turn`.

Step 5 is complete for the defined suite. Deployment and video remain pending.

## Default-suite result (without paid requests)

`uv run pytest -q`: **55 passed, 2 skipped**. All 57 cases were collected after the Anthropic compatibility regression was added.
`node tests/web_client_smoke.cjs`: passed (simulated DOM and transport).
`git diff --check`: passed for this change.

No paid API calls or real credentials were used in the default suite. Provider requests are mocked
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
| Actual browser appearance | John's screenshots of the local page and both provider responses | Desktop layout and successful provider responses confirmed; Stop not verified in a native browser |
| Real provider stream/usage | Two opt-in tests in `tests/test_live.py`; Dell `--live` run | Both passed on October 27 |

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

Expected default outcome: **55 passed, 2 skipped**. If tokenizer data is not
cached, allow its first-use download to finish. A download error is a failed
check, not permission to substitute a stub or silently skip validation.

Optional client smoke test, only if Node.js is installed:

```powershell
node tests/web_client_smoke.cjs
```

## Paid live checks — passed on the Dell October 27

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
John successfully accessed it in the observed live checks. Anthropic's pinned
API-version compatibility also passed. These results establish access for that
account and run, not a guarantee of future model availability.

Remaining limits: real provider errors/logging, network cancellation behavior,
mobile layout in a native browser, one-hour cache pricing, deployed behavior
and the required live video demo remain unverified. Tested sanitized error
paths do not guarantee third-party debug logs or monitoring that captures frame
locals are safe. Step 6 deployment has not started.

## October 26 follow-up: Anthropic temperature compatibility

John's Anthropic UI request failed with a sanitized generic provider error.
The screenshot does not expose the underlying HTTP status. Inspection found a
specific request incompatibility: SDK 2.3 defaults to API `2026-10-21`, but the
gateway also sends `temperature` through `extra_body`. That API version rejects
sampling parameters with HTTP 400, even for legacy models.

To preserve the assignment's temperature control, Haiku 4.5 requests now send
`extra_headers={"anthropic-version": "2023-06-01"}` alongside temperature.
This is the documented compatibility option; no dependency downgrade or model
change is required. See [Anthropic's migration guide](https://platform.claude.com/docs/en/api/migration-2026-10-21).

`tests/test_anthropic_transport.py` runs the actual SDK against a local HTTP mock,
rejects the former version/temperature combination and checks the serialized
version header, temperature body, SSE parsing and final usage. It failed before
the fix and passed afterward. This tests the real SDK's wire format but does not
establish live Anthropic account access. Default suite: **55 passed, 2 skipped**.
The earlier 54-pass Dell run remains valid historical evidence.

John also supplied a successful live OpenAI screenshot: 36 input tokens,
32 output tokens, TTFT 1911.6 ms, displayed throughput 15.4 tokens/sec and cost
$0.000025. It ended at the output-token limit. This verifies that UI request,
not the separate optional fifty-word live pytest case. The retry and live pytest
checks later succeeded, as recorded in the October 27 result above.
