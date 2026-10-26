# AI prompt and verification log

Student: John Nelson
Course: AD 331, Artificial Intelligence

## Workflow constraint

Work proceeds one assignment step at a time. Stop after Step 1 and wait for
John's instruction before generating the gateway prototype.

## Step 1: Environment setup

John created the public repository and authorized work with:

> I have created the repo. You may now proceed.

Actions taken by the AI assistant:

- Cloned the existing repository and retained its `main` history.
- Initialized a `uv` application with Python 3.11 and Pydantic v2.
- Added the assignment's runtime libraries and a separate development group
  for `pytest` and `pytest-asyncio`.
- Created placeholder modules matching the assignment layout.
- Added `.env.example` with placeholder values and ignore rules for local secrets.
- Documented setup commands for Windows PowerShell.

These files are scaffolding. No provider requests have been made, no complete
gateway exists yet, and the test modules do not contain executable tests yet.
Environment checks do not establish that live integration tests pass.

### Environment verification

- `uv sync --locked` completed successfully.
- Python 3.11.17 and Pydantic 2.14.1 were verified in the project environment.
- All requested runtime and development packages imported successfully.
- Official `AsyncOpenAI` and `AsyncAnthropic` classes imported without creating
  clients or making provider requests.
- Local secrets and `.venv` are ignored; `.env.example` and `uv.lock` remain
  trackable. Required scaffold files are present.

## Step 2: Initial AI prototype

Pending John's instruction. Record the actual generation prompt and retain
the initial implementation or its Git commit so the audit can refer to real
before-and-after code.

## Step 3: Manual audit and fixes

Pending an initial prototype and John's review. Document real findings with
file names, affected lines or commits, evidence, and before-and-after diffs.
Do not invent defects or claim a manual student review has already occurred.

## Steps 4-6: Interface, QA, deployment

Pending. Record commands, observed results, and any live-provider verification
separately from mocked tests as implementation proceeds.
