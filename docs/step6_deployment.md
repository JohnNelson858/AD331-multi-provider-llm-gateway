# Step 6: Local Docker deployment (Option B)

John Nelson · AD 331 · Verified on the Dell October 27, 2026

## Deployment choice and status

This implements the assignment's **Option B: Local Web Server Demo**, with a
Dockerfile and docker-compose.yml. The app stays on the Dell; the video will
show its end-to-end behavior. There is no public deployment URL.

**Step 6 complete: verified on John's Dell.** John supplied screenshots confirming
Docker/Compose availability, the Linux engine, successful quiet Compose
validation, a healthy running service on loopback port 8000, successful responses
from both providers, and an empty service list after shutdown. The assistant
reviewed the evidence; it did not run Docker on the Dell or receive API keys.
The separate 57-pass live pytest run used the local Python environment.

## Files and behavior

- `Dockerfile`: Python 3.11, uv 0.13.4 in a builder stage, locked runtime packages
  without pytest, and a separate non-root runtime. Application source and web
  assets are included. The tokenizer vocabulary is downloaded at build time so
  first inference does not need to write vocabulary files to the container.
- `.dockerignore`: allowlists build inputs and excludes host environments,
  credentials, git history, caches, tests and docs. No `COPY . .` is used.
- `docker-compose.yml`: publishes **127.0.0.1:8000**, mounts the local `.env` as
  a read-only Compose secret at `/app/.env`, and starts one Uvicorn worker.
  The container root filesystem is read-only, with a temporary `/tmp`; Linux
  capabilities are dropped. Containers do not automatically restart.
- Health check: reads `/api/models` locally. A healthy container proves the app
  is serving HTTP, not that provider keys, billing or model access work.

Uvicorn listens on `0.0.0.0` **inside the container** so Docker can forward traffic.
The published host port binds only to loopback. Open the browser on the Dell at
<http://127.0.0.1:8000>. Host/origin checks remain enabled.

Keys are not build arguments or image environment settings. The app loads them
from the mounted dotenv file when it starts. Compose file-backed secrets are
local file mounts, not an encrypted external vault; people with local Docker
administrative access remain trusted. Never display `.env`, run a command that
prints its contents, or include it in a screen recording.

## 1. Verify Docker Desktop

In PowerShell (these commands work from any folder):

```powershell
docker --version
docker compose version
```

If the commands are not recognized, follow the official
[Docker Desktop for Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).
Use Linux containers with the WSL 2 backend for this image. Start Docker Desktop
and wait until its engine is running. After installation, reopen PowerShell.
If Docker reports a WSL prerequisite problem, follow its exact displayed
instructions and the official guide; a restart may be needed.

Verify the engine is reachable:

```powershell
docker info --format '{{.OSType}}'
```

Expected: `linux`. A CLI version alone does not establish that the engine works.

## 2. Pull the container files

Stop a separately running Uvicorn process with Ctrl+C before using port 8000.

```powershell
cd "C:\Users\20joh\OneDrive\Documents\GitHub\AD331-multi-provider-llm-gateway"
git pull --ff-only
docker compose config --quiet
```

Keep your existing `.env` containing the two keys. Do not overwrite it with the
example. Compose needs this file for the runtime secret mount. Do not commit it.
The quiet validation command checks the Compose configuration without dumping
configuration values into the terminal.

## 3. Build and launch

```powershell
docker compose up --build -d --wait
docker compose ps
```

The first build downloads base images, locked packages and tokenizer vocabulary;
allow several minutes and keep Docker Desktop running. A build makes no paid
inference requests and needs no API keys in the image. The running container
reads the local keys when it starts. Expected service: `gateway`, running and
healthy, with `127.0.0.1:8000` published.

Open <http://127.0.0.1:8000>. `-d` runs the app in the background, so PowerShell
remains available. Closing the browser does not stop the container.

## 4. Verify end-to-end behavior

These are **paid** provider requests, separate from the free local health check.
Use the same short prompt once per provider with maximum output tokens **64**:

> Explain an async generator in one short sentence.

Select OpenAI, submit, and observe streamed text and FINAL usage. Then select
Anthropic and do the same. Confirm that TTFT, tokens/sec, prompt/completion counts
and the six-decimal USD cost appear. Save or share only the result screenshots,
not your credentials. Report errors rather than repeatedly retrying blindly.

Optional image check, without mounting any secrets or enabling network access:

```powershell
docker run --rm --network none --entrypoint python ad331-llm-gateway:local -c "from pathlib import Path; print('Embedded .env:', Path('/app/.env').exists())"
```

Expected: `Embedded .env: False`. This specifically checks the known dotenv path;
it is not a complete image/history credential scan. The Compose container has
that file at runtime because Compose supplies the secret mount.

## 5. Stop and restart

Stop and remove the container/network after practice or recording:

```powershell
docker compose down
```

The local `.env`, source files, API credits and built image remain available.
For another session without source changes:

```powershell
docker compose up -d --wait
```

After code changes, use `docker compose up --build -d --wait` to rebuild. After
changing keys in `.env`, restart the service to reload them:

```powershell
docker compose restart gateway
```

## Troubleshooting

| Symptom | Next check |
| --- | --- |
| Docker command missing | Install/open Docker Desktop, then reopen PowerShell |
| Engine connection or named-pipe error | Start Docker Desktop and wait for the Linux engine |
| Port 8000 already allocated | Stop the original Uvicorn process or existing container using that port |
| `.env` secret file missing | Confirm the file exists in the repository root on the Dell; do not create a directory named `.env` |
| Permission denied reading `.env` | On Linux, check local file permissions for the container's UID 10001; do not make credentials writable/public as a workaround |
| Build download failure | Check network/proxy/registry access; share the error without credentials |
| Health check fails | Run `docker compose logs --tail 50 gateway` and share the static startup/error output after checking for private data |
| Page works but provider fails | Check the app's typed error, local key, account balance and model access; health does not test providers |

This setup is for a local course demonstration. Public hosting would need a
separate design for authentication, quotas and deployment secrets.

## Verification record — October 27, 2026

- [x] Docker Desktop/Linux engine verified on the Dell.
- [x] `docker compose config --quiet` passed.
- [x] Image built and service reported healthy.
- [x] Page opened through Docker's published port.
- [x] OpenAI returned text with FINAL usage inside Docker.
- [x] Anthropic returned text with FINAL usage inside Docker.
- [x] Container stopped using `docker compose down`.

Step 6 is complete based on the supplied Dell evidence. Docker reported version
29.9.2, Compose v5.6.1, and engine OS `linux`. The Compose service was
`ad331-llm-gateway-gateway-1`, image `ad331-llm-gateway:local`, with healthy status
and port `127.0.0.1:8000->8000/tcp`.

The same prompt and 64-token maximum were used for these container UI checks:

| Provider/model | Input tokens | Output tokens | TTFT (ms) | Displayed tokens/sec | Calculated USD cost | Finish |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| OpenAI / gpt-4o-mini | 16 | 32 | 2631.1 | 11.4 | $0.000022 | stop |
| Anthropic / claude-haiku-4-5-20251001 | 17 | 45 | 884.9 | 33.3 | $0.000242 | end_turn |

Both displayed FINAL provider-reported usage, with zero cache reads/writes.
These are observations from individual requests, not a controlled performance
benchmark or invoice reconciliation. The final `docker compose ps` screenshot
showed only column headings, confirming no remaining service after shutdown.

The optional image dotenv-path check was not shown and is not claimed as
executed. The image design excludes dotenv files, but this record does not
claim a complete image/history credential scan. Native-browser Stop behavior,
one-hour cache accounting and public-hosting behavior remain outside the
verified scope.

## Recording and submission

For the assignment video, show the Docker files, launch/healthy service, both
providers, audit findings, sanitized error behavior, and pytest results. Keep the
webcam visible and the total video between 5:00 and 7:00. Use existing live QA
results as evidence rather than describing skipped default tests as live checks.
If rerunning `--live` for recording, it creates two more paid requests.

Submission deployment entry: **Local Docker demo (Option B)**.
The GitHub repository and unlisted/public YouTube video URL are still required.
A local loopback URL is not an instructor-accessible public deployment URL.

References:
[uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/),
[Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets),
[Compose service reference](https://docs.docker.com/reference/compose-file/services/).
