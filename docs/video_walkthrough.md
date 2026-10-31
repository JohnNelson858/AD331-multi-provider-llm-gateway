# John Nelson — video walkthrough guide

AD 331 · Multi-Provider Async LLM Gateway & Real-Time Telemetry Engine

**Target: 6:15. Required final duration: 5:00–7:00.** This is a live application
walkthrough; a slide deck is not required for this assignment. This guide belongs
to the gateway project, not the separate LLM-foundations slide assignment.

Use the narration as speaking notes. Read only the **Say** passages; actions,
commands and headings are not spoken. Rehearse with the actual screen changes.
Timing is a target, not a measured recording. Do not claim a request or test
passed until its result is visible.

## Run of show

| Time | Section | What the viewer should see |
| --- | --- | --- |
| 0:00–0:55 | Introduction and architecture | Show the README architecture diagram, the VS Code Explorer folders, then src/gateway.py at UnifiedLLMGateway.stream. Briefly show docker compose ps with healthy status. |
| 0:55–2:20 | AI generation and two concrete audit findings | Open docs/step2_generation_prompt.md, then ai_prompt_log.md at Step 3 findings 1 and 3. Show each Before and After code block rather than scrolling through the entire log. |
| 2:20–3:55 | Live streaming and provider switching | Use the Docker app at port 8000. Submit the shared prompt once with OpenAI, then once with Anthropic; wait for FINAL each time. Point to TTFT, counts and cost, using the actual new values. |
| 3:55–5:10 | Credential error and browser/log inspection | Switch to the prepared port-8001 tab with the intentionally invalid environment value. Select OpenAI and submit the same prompt. Show AuthenticationError, DevTools Network request/response for api/stream, then the dedicated terminal startup/log view. |
| 5:10–5:55 | Run QA and explain scope | In the MAIN PowerShell window, run uv run pytest -v --live immediately, then speak while it executes. Show the final summary. Do not run this in the invalid-key terminal. |
| 5:55–6:15 | Close with deployment and engineering takeaway | Return to the Docker app or README. Keep the webcam visible. Stop the recording near 6:15, then stop services after recording. |

## Prepare before recording

### 1. Start the verified Docker app

Open Docker Desktop and wait for the engine. In a MAIN PowerShell window:

```powershell
cd "C:\Users\20joh\OneDrive\Documents\GitHub\AD331-multi-provider-llm-gateway"
git pull --ff-only
docker compose up -d --wait
docker compose ps
```

The image is already built. If it has been deleted or app source has changed,
use `docker compose up --build -d --wait` before recording. Do not spend the
video's time budget downloading/building images.

Open http://127.0.0.1:8000. Confirm the page is loaded, select OpenAI, set the
output limit to **64**, and prepare this exact prompt:

> Explain an async generator in one short sentence.

Do not submit during setup unless you want another paid practice request.

### 2. Prepare a separate invalid-credential instance

Open a **second PowerShell window**. Keep this instance separate from MAIN.

```powershell
cd "C:\Users\20joh\OneDrive\Documents\GitHub\AD331-multi-provider-llm-gateway"
$env:OPENAI_API_KEY = "DEMO_INVALID_KEY"
uv run uvicorn src.app:app --host 127.0.0.1 --port 8001 --no-access-log
```

This is a deliberately invalid local value, not a real key. It applies to this
PowerShell process and its child only. The app loads `.env` with `override=False`,
so this invalid value wins for this second server. It does not alter the `.env`
file, the Docker container, your saved keys, or your subscription.

Open http://127.0.0.1:8001 in another browser tab. Select OpenAI and enter the same
prompt. Local validation rejects `DEMO_INVALID_KEY` before SDK client creation,
so this demonstration does not make a provider inference request. Describe it
honestly as **local credential validation**, not a live provider rejection.

Practice this failure once before the recording. Expect AuthenticationError,
no text, and INCOMPLETE metrics. Refresh the tab afterward to reset the visible
error. If the expected behavior does not appear, stop and troubleshoot before
recording. This exact second-server rehearsal has not yet been verified on the
Dell; its behavior follows the existing tested validation path.

Do not replace this with editing your real `.env` on camera. Do not use `setx`.
Keep the invalid-key server running for the security segment. Run final QA in
MAIN, never in this invalid-key window.

### 3. Arrange the screen evidence

- VS Code: open README.md, docs/step2_generation_prompt.md, ai_prompt_log.md,
  src/gateway.py, src/schemas.py, src/pricing.py, and docker-compose.yml.
- Use the README's rendered architecture diagram or its GitHub view. For the
  audit, bookmark finding 1 (usage updates) and finding 3 (exception context).
- Browser tab A: working Docker app on **8000**. Tab B: invalid-key instance on
  **8001**. Check the selected provider before each submission.
- In tab B's developer tools, use Network and select the `/api/stream` request
  after submitting. Inspect request payload/headers and the event response. The
  application request does not carry either provider key. Do not open storage,
  files or unrelated requests that could contain personal information.
- Keep MAIN ready for `uv run pytest -v --live`. Keep the second terminal ready
  to show only the invalid-instance startup/log area.
- Close `.env`, API-key pages, payment pages and private tabs. Disable desktop
  notification banners. Use a readable editor font and leave room for the webcam.
- Put this guide on paper, a phone or an unshared display so it is not the main
  content of the screencast. Look toward the camera at transitions.

## Recording with Zoom on your Dell

1. Open Zoom's desktop app and its Recording settings. Enable **Record video
   during screen sharing**. For a corner overlay, disable **Place video next to
   the shared screen** (some versions label the option **Show video and screen
   share side-by-side**). Keep the camera thumbnail clear of code and metrics.
2. Start a meeting by yourself as host, turn on the webcam, and select the correct
   microphone. Share the screen containing the app/editor/terminals. Keep sharing
   active throughout so screen and face stay visible during window changes.
3. Select **Record**, then **Record on this Computer** if asked. Computer
   recording is available with a free Zoom account; cloud recording is not needed.
4. FIRST record a 15–20 second test of screen + face + voice, then play the saved
   MP4. Verify the webcam is actually in the recording, not merely visible in the
   meeting preview. Adjust the layout if it covers the telemetry.
5. Record the full take. At the end, stop recording and end the meeting; let Zoom
   finish converting the MP4 before closing the laptop. Use a local recording
   folder rather than a OneDrive-synced folder during conversion.

Official Zoom references:
[Recording layouts](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062314),
[Recording settings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060612),
[Computer recording](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0076922).

## Timed narration and actions

### 1. 0:00–0:55 — Introduction and architecture

**Show/do:** Show the README architecture diagram, the VS Code Explorer folders, then src/gateway.py at UnifiedLLMGateway.stream. Briefly show docker compose ps with healthy status.

**Say:**

Hi, I'm John Nelson, and this is my AD 331 multi-provider LLM gateway. I built it with AI assistance, reviewed the generated code, and tested it with both OpenAI and Anthropic.

The browser sends a prompt to FastAPI. The gateway calls the selected provider asynchronously and converts its events into the same Pydantic stream format. Server-Sent Events carry the text and metrics back to the page.

The main files separate the gateway, schemas, pricing, and interface. One gateway maintains reusable clients, while each request has its own counters. Tokenizer work runs in a worker thread. For deployment, I'm using the assignment's local Docker option; this service is running and healthy.

### 2. 0:55–2:20 — AI generation and two concrete audit findings

**Show/do:** Open docs/step2_generation_prompt.md, then ai_prompt_log.md at Step 3 findings 1 and 3. Show each Before and After code block rather than scrolling through the entire log.

**Say:**

My generation record preserves the assignment prompt and explains how ChatGPT produced the initial draft. The original version remains in Git history, so the audit shows actual changes.

The first bug involved Anthropic's usage updates. The draft handled later output counts but ignored updated input and cache counts. That could leave the final token total and cost wrong. The replacement helper handles all supplied usage fields. Because these are cumulative snapshots, it replaces earlier values instead of adding them together, and it retains fields that are omitted.

The second issue involved exception privacy. Raising a sanitized error with “from None” hides the original traceback chain, but the original exception remains attached through its context. That can expose provider details to an exception serializer. The fix creates a safe domain error inside the handler and raises it after the handler ends. Regression tests check that a fake secret is absent from the public error and its chain.

Live testing also caught an Anthropic API-version mismatch. The documented compatible version now preserves temperature support for this legacy Haiku model.

### 3. 2:20–3:55 — Live streaming and provider switching

**Show/do:** Use the Docker app at port 8000. Submit the shared prompt once with OpenAI, then once with Anthropic; wait for FINAL each time. Point to TTFT, counts and cost, using the actual new values.

**Say:**

Here I'm sending the same short prompt to OpenAI, with a sixty-four-token output limit. The response appears in fragments as they arrive; a network fragment is not necessarily one token.

The dashboard measures time to the first nonempty text, input and output tokens, generation speed, and cost. Speed here is output tokens divided by total request duration, so it includes startup latency. It is not a decode-only benchmark.

Now I'll switch to Anthropic and send the same prompt. The interface uses the same event format even though Anthropic's underlying stream differs.

While the request runs, the figures are provisional. FINAL means complete provider usage has arrived. The cost calculation uses Decimal internally and displays six decimal places. It uses configured rates rather than claiming invoice reconciliation. These two requests let me compare observed latency and cost, but one pair of responses is not a general benchmark.

**Action order:** Send with OpenAI on port 8000 → wait for FINAL → point out
metrics → switch to Anthropic → send identical prompt → wait for FINAL. Keep
speaking during the wait. If either fails, do not describe it as success.

### 4. 3:55–5:10 — Credential error and browser/log inspection

**Show/do:** Switch to the prepared port-8001 tab with the intentionally invalid environment value. Select OpenAI and submit the same prompt. Show AuthenticationError, DevTools Network request/response for api/stream, then the dedicated terminal startup/log view.

**Say:**

For this error demonstration, I started a second local instance on port eight thousand one. Only that instance has an intentionally invalid credential value. The Docker instance still has its working configuration, and I have not edited or displayed either real key.

When I submit, local validation returns an AuthenticationError before contacting the provider. The page shows a readable message and an incomplete state instead of crashing or inventing final metrics.

In the browser's network view, the request contains the prompt and settings, and the response contains the sanitized error. Neither contains an API key. The server view also avoids displaying a raw exception traceback for this failure. Separate tests cover secret-bearing authentication, rate-limit, and connection errors from both SDKs.

### 5. 5:10–5:55 — Run QA and explain scope

**Show/do:** In the MAIN PowerShell window, run uv run pytest -v --live immediately, then speak while it executes. Show the final summary. Do not run this in the invalid-key terminal.

**Say:**

I'm now running the full test suite, including the two explicitly enabled live provider checks. The tests cover normalized streams, real tokenizer comparisons, timing, Decimal pricing, malformed credentials, secret handling, and client cleanup.

The OpenAI live test compares the fixed prompt's local token count with billed input within ten percent. Anthropic is checked using its own provider usage, not OpenAI's tokenizer.

My verified run passed all fifty-seven tests. I'll confirm this new run's result on screen before closing.

**Run in MAIN:**

```powershell
uv run pytest -v --live
```

When it finishes, if it passes, say: **“All fifty-seven tests passed, including
both live provider checks.”** If a different result appears, investigate before
recording the final take. The previous 18.50-second duration is historical, not
a promised duration for a new run. If the tests finish slowly, retain the result
and adjust the rehearsal; never say they passed while they are still running.

### 6. 5:55–6:15 — Close with deployment and engineering takeaway

**Show/do:** Return to the Docker app or README. Keep the webcam visible. Stop the recording near 6:15, then stop services after recording.

**Say:**

This project combines a shared async interface, provider-reported final usage, and deliberate error handling. The audit and live tests show why generated code needs verification. Both providers work in the local Docker deployment. Thank you.

## Rehearsal, timing and costs

The planned take uses **four paid inference requests**: two UI submissions capped
at 64 output tokens each, and the two live test cases capped at 32 output tokens
each. Input tokens are also billed. Additional practice submissions cost extra.
The invalid-shape credential demonstration is blocked locally before inference.
Do not repeatedly rerun successful live tests just to improve delivery.

Practice once with a stopwatch. Natural pauses and screen actions count toward
the video duration. Aim to start each section near its cue. If you finish before
5:00, add a meaningful walkthrough of the stream schema or pricing formula. If
longer than 7:00, shorten narration and navigation; do not speed-read. Leave a
buffer for model/network delays. A 6:00–6:30 rehearsal is a useful target.

For the live metrics, describe what the new request actually shows. Do not read
old screenshot numbers as if they belong to the recording. FINAL indicates
complete accounting; a length/max_tokens finish can still mean a cut-off answer.
Use the end-of-response reason to distinguish normal completion from truncation.

The two main audit findings are sufficient. If navigation is slow, shorten the
extra API-version sentence; keep both before/after explanations and the live
provider/error/test demonstrations. A title slide is optional and unnecessary.

## Delivery reminders

Say “time to first token” before using TTFT. Say “server-sent events” rather than
reading the abbreviation SSE. Point to each relevant field instead of reciting
all filenames or every changing number. Pause briefly at a completed response
and at the final test result. Speak as the student who reviewed and demonstrated
the system; do not claim an employer role or sole authorship of the AI-generated
code. A small natural pause is preferable to rushing through the explanation.

## After recording

In the invalid-key terminal, press Ctrl+C and close that window. Closing the
window discards its process-local invalid credential override. In MAIN:

```powershell
docker compose down
```

Do not commit `.env`, change your real keys for the recording, or publish raw
provider responses containing private data. None of the guide's preparation
commands modifies the working key file.

## Final review checklist

- [ ] MP4 is between 5:00 and 7:00, verified in the player.
- [ ] Webcam and screen are visible throughout; microphone is clear.
- [ ] Architecture and source layout are shown.
- [ ] Actual AI generation record is shown; authorship is described honestly.
- [ ] Two real audit findings and exact before/after code are visible.
- [ ] Same prompt is submitted live to OpenAI and Anthropic in Docker.
- [ ] Final TTFT, throughput, counts and six-decimal cost are visible.
- [ ] Invalid credential value produces a readable typed error; demo's scope is clear.
- [ ] Browser network details and server output show no keys or raw traceback for that failure.
- [ ] QA runs on screen; the result is described accurately.
- [ ] No real keys, `.env` contents, payment details or private notifications appear.
- [ ] Upload as Unlisted or Public; verify playback permissions before submitting.

## Canvas submission text (fill after upload)

Student Name: John Nelson
GitHub Repository URL: https://github.com/JohnNelson858/AD331-multi-provider-llm-gateway
Deployment: Local Docker demo (Option B); demonstrated in the recording
YouTube Video Link: [paste your video URL]
Duration: [MM:SS from the finished MP4]
Supported Models: OpenAI gpt-4o-mini; Anthropic claude-haiku-4-5-20251001
Verification: 57 tests passed in the verified October 27 run, including both live providers.

If you rerun tests for the recording, update the verification sentence to the
observed result. A local `127.0.0.1` address is not a public deployment link.

## Scope of this preparation

The script is based on the checked-in implementation and John's previously
verified 57-test run and Docker/provider screenshots. No new paid requests were
made to prepare it. The script has not been recorded, voice-timed, or rehearsed
on the Dell. Native-browser network/log inspection and the port-8001 rehearsal
still require John's observation; this guide does not claim them already done.
