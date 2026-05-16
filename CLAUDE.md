# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-file Python daemon (`watcher.py`) that streams Docker events via the Docker socket and sends Telegram alerts when containers die, OOM, or go unhealthy. No framework, no database — just one loop.

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

`watcher.py` is the entire application. On startup, a daemon thread runs `watch_disk()` and the main thread runs the Docker event loop.

- `watch()` — opens `client.events()` stream filtered to `die`, `oom`, `health_status` events; dispatches to handlers
- `handle_die` — distinguishes graceful (exit 0/143) from crash; sends colored Telegram message
- `handle_oom` / `handle_unhealthy` — simple Telegram notifications
- `watch_disk()` — polls `shutil.disk_usage` every `DISK_CHECK_INTERVAL` seconds; sends one alert when a path crosses `DISK_WARN_PERCENT`, then stays silent until it drops back below (avoids spam)
- `send()` — posts to Telegram Bot API with HTML parse mode
- Outer `while True` reconnect loop restarts `watch()` if the Docker daemon restarts or the socket drops

`WATCHER_IGNORE` env var (comma-separated container names) prevents alerts for known-benign containers (default: `certbot`).

## Dependencies

Pinned in Dockerfile: `docker==7.1.0`, `requests==2.32.3`. No `requirements.txt` — update pins directly in `Dockerfile`.
