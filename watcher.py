import os
import time
import docker
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
IGNORED = set(
    c.strip()
    for c in os.environ.get("WATCHER_IGNORE", "certbot").split(",")
    if c.strip()
)

# Exit codes that indicate an intentional/graceful stop
GRACEFUL_EXIT_CODES = {"0", "143"}  # 143 = 128 + SIGTERM


def send(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[watcher] telegram error: {e}", flush=True)


def handle_die(attrs: dict, ts: str) -> None:
    name = attrs.get("name", "unknown")
    image = attrs.get("image", "?")
    exit_code = attrs.get("exitCode", "?")

    if exit_code in GRACEFUL_EXIT_CODES:
        emoji = "🟡"
        label = "parou (graceful)"
    else:
        emoji = "🔴"
        label = "crashou"

    send(
        f"{emoji} <b>{name}</b> {label}\n"
        f"Exit code: <code>{exit_code}</code>\n"
        f"Imagem: <code>{image}</code>\n"
        f"⏰ {ts}"
    )


def handle_oom(attrs: dict, ts: str) -> None:
    name = attrs.get("name", "unknown")
    send(f"💀 <b>{name}</b> morreu por OOM (sem memória)\n⏰ {ts}")


def handle_unhealthy(attrs: dict, ts: str) -> None:
    name = attrs.get("name", "unknown")
    send(f"⚠️ <b>{name}</b> está <b>unhealthy</b>\n⏰ {ts}")


def watch() -> None:
    client = docker.from_env()
    send("👀 <b>docker-watcher</b> iniciado — monitorando containers")
    print("[watcher] started", flush=True)

    for event in client.events(
        decode=True,
        filters={"event": ["die", "oom", "health_status"]},
    ):
        # Docker API >= 1.22 uses "Action"; older versions use "status"
        status: str = event.get("Action") or event.get("status", "")
        attrs: dict = event.get("Actor", {}).get("Attributes", {})
        name: str = attrs.get("name", "")
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(event.get("time", 0)))

        if name in IGNORED:
            continue

        print(f"[watcher] event={status} container={name}", flush=True)

        if status == "die":
            handle_die(attrs, ts)
        elif status == "oom":
            handle_oom(attrs, ts)
        elif status == "health_status: unhealthy":
            handle_unhealthy(attrs, ts)


if __name__ == "__main__":
    # Reconnect loop — if Docker daemon restarts, events() will raise
    while True:
        try:
            watch()
        except Exception as e:
            print(f"[watcher] error: {e} — reconnecting in 5s", flush=True)
            time.sleep(5)
