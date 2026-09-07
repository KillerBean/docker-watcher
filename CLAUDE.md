# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Python daemon (`watcher.py`) that streams Docker events via the Docker socket
and sends Telegram alerts when containers die, OOM, or go unhealthy. No
framework or database.

## Running locally

```bash
# Requires Docker socket access and env vars set
cp .env.example .env  # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python watcher.py
```

## Build & deploy

```bash
docker compose build docker-watcher
docker compose up -d docker-watcher
```

The container mounts `/var/run/docker.sock:ro` to receive host Docker events.

## Architecture

`watcher.py` contains the application. On startup, a daemon thread runs
`watch_disk()` and the main thread supervises the Docker event loop.

- `watch()` — opens `client.events()` filtered to `die`, `oom`, `health_status`; dispatches validated events
- `process_event()` — rejects malformed events, applies `WATCHER_IGNORE`, and records counters
- `TelegramNotifier` — escapes/bounds messages, applies the alert rate limit and records send/failure/drop counters
- `watch_disk()` — polls `shutil.disk_usage` and deduplicates a warning until the path recovers
- `run()` — reconnects after stream failure with bounded exponential backoff and jitter

`WATCHER_IGNORE` env var (comma-separated container names) prevents alerts for known-benign containers (default: `certbot`).

## Dependencies

Pinned in `requirements.txt`: `docker==7.1.0`, `requests==2.32.3`.

## Tests

```bash
python -m unittest discover -s tests -v
python -m py_compile watcher.py
```

Security and operational guidance live in `docs/security/THREAT-MODEL.md` and
`docs/ops/RUNBOOKS.md`.
