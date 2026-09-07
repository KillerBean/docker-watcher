"""Docker event watcher with Telegram notifications."""

from __future__ import annotations

import html
import os
import random
import shutil
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests

try:
    import docker
except ImportError:  # Allows unit tests to run without a Docker daemon/SDK.
    docker = None  # type: ignore[assignment]


TELEGRAM_MAX_MESSAGE_LENGTH = 4096
DEFAULT_IGNORED = "certbot"
GRACEFUL_EXIT_CODES = {"0", "143"}  # 143 = 128 + SIGTERM
Notify = Callable[[str], bool]


class Metrics:
    """Small thread-safe counter set emitted through the process log."""

    _NAMES = (
        "events_seen",
        "events_ignored",
        "events_malformed",
        "alerts_sent",
        "alerts_failed",
        "alerts_dropped",
        "disk_check_failures",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values = {name: 0 for name in self._NAMES}

    def increment(self, name: str) -> None:
        with self._lock:
            if name in self._values:
                self._values[name] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)

    def log(self) -> None:
        values = self.snapshot()
        fields = " ".join(f"{key}={value}" for key, value in values.items())
        print(f"[metrics] {fields}", flush=True)


class AlertRateLimiter:
    """Per-process sliding-window limiter to contain event storms."""

    def __init__(
        self, limit_per_minute: int = 30, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if limit_per_minute < 1:
            raise ValueError("limit_per_minute must be positive")
        self.limit_per_minute = limit_per_minute
        self._clock = clock
        self._sent_at: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = self._clock()
        with self._lock:
            while self._sent_at and now - self._sent_at[0] >= 60:
                self._sent_at.popleft()
            if len(self._sent_at) >= self.limit_per_minute:
                return False
            self._sent_at.append(now)
            return True


class TelegramNotifier:
    """Telegram transport with bounded messages, metrics and rate limiting."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        metrics: Metrics | None = None,
        limiter: AlertRateLimiter | None = None,
        post: Callable[..., Any] = requests.post,
        timeout: int = 10,
    ) -> None:
        if not token or not chat_id:
            raise ValueError("Telegram token and chat id are required")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._metrics = metrics or Metrics()
        self._limiter = limiter or AlertRateLimiter()
        self._post = post
        self._timeout = timeout

    def send(self, text: str) -> bool:
        if not self._limiter.allow():
            self._metrics.increment("alerts_dropped")
            print("[telegram] alert dropped: rate limit", flush=True)
            return False

        # Handlers escape dynamic values before adding Telegram markup.  The
        # fallback keeps an unexpected oversized message valid HTML.
        if len(text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            text = bounded_html_escape(text, TELEGRAM_MAX_MESSAGE_LENGTH)

        try:
            response = self._post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            self._metrics.increment("alerts_sent")
            return True
        except (requests.RequestException, ValueError, AttributeError) as exc:
            self._metrics.increment("alerts_failed")
            print(f"[telegram] transport failure: {type(exc).__name__}", flush=True)
            return False


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: str
    ignored: frozenset[str]
    disk_warn_percent: int
    disk_check_interval: int
    disk_paths: tuple[str, ...]
    alert_rate_limit: int
    metrics_interval: int
    reconnect_initial_delay: float
    reconnect_max_delay: float
    reconnect_jitter: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        values = env if env is not None else os.environ

        def integer(name: str, default: str, minimum: int) -> int:
            try:
                result = int(values.get(name, default))
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if result < minimum:
                raise ValueError(f"{name} must be >= {minimum}")
            return result

        def number(name: str, default: str, minimum: float) -> float:
            try:
                result = float(values.get(name, default))
            except ValueError as exc:
                raise ValueError(f"{name} must be a number") from exc
            if result < minimum:
                raise ValueError(f"{name} must be >= {minimum}")
            return result

        paths = tuple(
            path.strip()
            for path in values.get("DISK_PATHS", "/").split(",")
            if path.strip()
        )
        if not paths:
            raise ValueError("DISK_PATHS must contain at least one path")

        warn_percent = integer("DISK_WARN_PERCENT", "80", 1)
        if warn_percent > 100:
            raise ValueError("DISK_WARN_PERCENT must be <= 100")

        jitter = number("RECONNECT_JITTER", "0.2", 0)
        if jitter > 1:
            raise ValueError("RECONNECT_JITTER must be <= 1")

        return cls(
            telegram_token=values.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=values.get("TELEGRAM_CHAT_ID", "").strip(),
            ignored=frozenset(
                item.strip()
                for item in values.get("WATCHER_IGNORE", DEFAULT_IGNORED).split(",")
                if item.strip()
            ),
            disk_warn_percent=warn_percent,
            disk_check_interval=integer("DISK_CHECK_INTERVAL", "300", 1),
            disk_paths=paths,
            alert_rate_limit=integer("WATCHER_ALERTS_PER_MINUTE", "30", 1),
            metrics_interval=integer("WATCHER_METRICS_INTERVAL", "60", 1),
            reconnect_initial_delay=number("RECONNECT_INITIAL_DELAY", "1", 0.1),
            reconnect_max_delay=number("RECONNECT_MAX_DELAY", "60", 0.1),
            reconnect_jitter=jitter,
        )


def escaped(value: Any, max_length: int = 256) -> str:
    """Bound and HTML-escape untrusted Docker metadata before interpolation."""

    text = str(value if value not in (None, "") else "?")
    return bounded_html_escape(text, max_length)


def bounded_html_escape(text: str, max_length: int) -> str:
    """Escape one character at a time so the encoded result also fits."""

    output: list[str] = []
    used = 0
    truncated = False
    for character in text:
        encoded = html.escape(character, quote=False)
        if used + len(encoded) >= max_length:
            truncated = True
            break
        output.append(encoded)
        used += len(encoded)
    if truncated and used < max_length:
        output.append("…")
    return "".join(output)


def event_timestamp(value: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(float(value)))
    except (TypeError, ValueError, OverflowError):
        return "unknown time"


def handle_die(attrs: Mapping[str, Any], ts: str, notify: Notify) -> None:
    name = escaped(attrs.get("name", "unknown"))
    image = escaped(attrs.get("image", "?"))
    exit_code = escaped(attrs.get("exitCode", "?"), max_length=32)

    if exit_code in GRACEFUL_EXIT_CODES:
        emoji, label = "🟡", "parou (graceful)"
    else:
        emoji, label = "🔴", "crashou"

    notify(
        f"{emoji} <b>{name}</b> {label}\n"
        f"Exit code: <code>{exit_code}</code>\n"
        f"Imagem: <code>{image}</code>\n"
        f"⏰ {escaped(ts, 64)}"
    )


def handle_oom(attrs: Mapping[str, Any], ts: str, notify: Notify) -> None:
    name = escaped(attrs.get("name", "unknown"))
    notify(f"💀 <b>{name}</b> morreu por OOM (sem memória)\n⏰ {escaped(ts, 64)}")


def handle_unhealthy(attrs: Mapping[str, Any], ts: str, notify: Notify) -> None:
    name = escaped(attrs.get("name", "unknown"))
    notify(f"⚠️ <b>{name}</b> está <b>unhealthy</b>\n⏰ {escaped(ts, 64)}")


def process_event(
    event: Any,
    ignored: frozenset[str] | set[str],
    notify: Notify,
    metrics: Metrics,
) -> bool:
    """Validate and dispatch one Docker event; malformed input is ignored."""

    if not isinstance(event, Mapping):
        metrics.increment("events_malformed")
        print("[watcher] malformed event: expected object", flush=True)
        return False

    status = event.get("Action") or event.get("status", "")
    actor = event.get("Actor", {})
    attrs = actor.get("Attributes") if isinstance(actor, Mapping) else None
    name = attrs.get("name") if isinstance(attrs, Mapping) else None
    if not isinstance(status, str) or not isinstance(attrs, Mapping) or not isinstance(name, str):
        metrics.increment("events_malformed")
        print("[watcher] malformed event: missing action/actor/name", flush=True)
        return False

    if name in ignored:
        metrics.increment("events_ignored")
        return False

    metrics.increment("events_seen")
    ts = event_timestamp(event.get("time"))
    print(f"[watcher] event={status} container={escaped(name)}", flush=True)

    if status == "die":
        handle_die(attrs, ts, notify)
    elif status == "oom":
        handle_oom(attrs, ts, notify)
    elif status == "health_status: unhealthy":
        handle_unhealthy(attrs, ts, notify)
    return True


def check_disk_once(
    paths: tuple[str, ...] | list[str],
    alerted: dict[str, bool],
    warn_percent: int,
    notify: Notify,
    metrics: Metrics,
    disk_usage: Callable[[str], Any] = shutil.disk_usage,
) -> None:
    for path in paths:
        try:
            usage = disk_usage(path)
            if usage.total <= 0:
                raise ValueError("disk total must be positive")
            pct = usage.used * 100 // usage.total
            over = pct >= warn_percent
            print(f"[disk] {escaped(path)} {pct}% used", flush=True)

            if over and not alerted[path]:
                free_gb = usage.free / 1024**3
                notify(
                    f"💾 <b>Disco quase cheio</b>: <code>{escaped(path)}</code>\n"
                    f"Uso: <b>{pct}%</b> (limite: {warn_percent}%)\n"
                    f"Livre: <code>{free_gb:.1f} GB</code>"
                )
                alerted[path] = True
            elif not over:
                alerted[path] = False
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            metrics.increment("disk_check_failures")
            print(f"[disk] erro ao checar {escaped(path)}: {exc}", flush=True)


def watch_disk(
    config: Config,
    notify: Notify,
    metrics: Metrics,
    stop_event: threading.Event,
    disk_usage: Callable[[str], Any] = shutil.disk_usage,
) -> None:
    alerted = {path: False for path in config.disk_paths}
    while not stop_event.is_set():
        check_disk_once(
            config.disk_paths,
            alerted,
            config.disk_warn_percent,
            notify,
            metrics,
            disk_usage,
        )
        stop_event.wait(config.disk_check_interval)


def report_metrics(metrics: Metrics, interval: int, stop_event: threading.Event) -> None:
    while not stop_event.wait(interval):
        metrics.log()


def watch(
    config: Config,
    notify: Notify,
    metrics: Metrics,
    client_factory: Callable[[], Any] | None = None,
) -> None:
    if client_factory is None:
        if docker is None:
            raise RuntimeError("Docker SDK is not installed")
        client_factory = docker.from_env

    client = client_factory()
    notify("👀 <b>docker-watcher</b> iniciado — monitorando containers")
    print("[watcher] started", flush=True)

    for event in client.events(
        decode=True,
        filters={"event": ["die", "oom", "health_status"]},
    ):
        process_event(event, config.ignored, notify, metrics)


def reconnect_delay(
    attempt: int,
    initial: float,
    maximum: float,
    jitter: float,
    random_value: Callable[[], float] = random.random,
) -> float:
    base = initial
    for _ in range(attempt):
        base = min(maximum, base * 2)
        if base >= maximum:
            break
    return min(maximum, base + base * jitter * random_value())


def run(
    config: Config,
    *,
    client_factory: Callable[[], Any] | None = None,
    notifier: TelegramNotifier | None = None,
    stop_event: threading.Event | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> None:
    metrics = Metrics()
    stop = stop_event or threading.Event()
    telegram = notifier or TelegramNotifier(
        config.telegram_token,
        config.telegram_chat_id,
        metrics=metrics,
        limiter=AlertRateLimiter(config.alert_rate_limit),
    )
    notify = telegram.send

    disk_thread = threading.Thread(
        target=watch_disk,
        args=(config, notify, metrics, stop),
        name="disk-watcher",
        daemon=True,
    )
    disk_thread.start()

    attempt = 0
    metrics_thread = threading.Thread(
        target=report_metrics,
        args=(metrics, config.metrics_interval, stop),
        name="metrics-reporter",
        daemon=True,
    )
    metrics_thread.start()
    try:
        while not stop.is_set():
            try:
                watch(config, notify, metrics, client_factory)
                print("[watcher] event stream ended; reconnecting", flush=True)
                attempt = 0
            except Exception as exc:  # Last-resort supervisor boundary.
                print(f"[watcher] error: {exc}", flush=True)

            delay = reconnect_delay(
                attempt,
                config.reconnect_initial_delay,
                config.reconnect_max_delay,
                config.reconnect_jitter,
                random_value,
            )
            print(f"[watcher] reconnecting in {delay:.2f}s", flush=True)
            sleep(delay)
            attempt += 1
    finally:
        stop.set()
        metrics.log()


def main() -> None:
    config = Config.from_env()
    if not config.telegram_token or not config.telegram_chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    run(config)


if __name__ == "__main__":
    main()
