import unittest
from types import SimpleNamespace

from watcher import (
    AlertRateLimiter,
    Config,
    Metrics,
    TelegramNotifier,
    check_disk_once,
    process_event,
    reconnect_delay,
)


class Response:
    def __init__(self, error=None):
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class WatcherTests(unittest.TestCase):
    def test_die_classifies_graceful_exit_and_escapes_metadata(self):
        messages = []
        metrics = Metrics()

        process_event(
            {
                "Action": "die",
                "time": 1,
                "Actor": {
                    "Attributes": {
                        "name": "api<prod>&1",
                        "image": "image:tag&latest",
                        "exitCode": "0",
                    }
                },
            },
            frozenset(),
            lambda message: messages.append(message) or True,
            metrics,
        )

        self.assertEqual(metrics.snapshot()["events_seen"], 1)
        self.assertIn("parou (graceful)", messages[0])
        self.assertIn("api&lt;prod&gt;&amp;1", messages[0])
        self.assertIn("image:tag&amp;latest", messages[0])
        self.assertNotIn("api<prod>", messages[0])

    def test_malformed_event_is_ignored(self):
        messages = []
        metrics = Metrics()

        self.assertFalse(process_event({"Action": "die"}, frozenset(), messages.append, metrics))
        self.assertFalse(process_event("not-an-event", frozenset(), messages.append, metrics))

        self.assertEqual(messages, [])
        self.assertEqual(metrics.snapshot()["events_malformed"], 2)

    def test_ignored_container_does_not_alert(self):
        messages = []
        metrics = Metrics()
        process_event(
            {"Action": "oom", "Actor": {"Attributes": {"name": "certbot"}}},
            frozenset({"certbot"}),
            messages.append,
            metrics,
        )
        self.assertEqual(messages, [])
        self.assertEqual(metrics.snapshot()["events_ignored"], 1)

    def test_disk_alert_is_deduplicated_until_recovery(self):
        messages = []
        metrics = Metrics()
        alerted = {"/data": False}
        usages = iter(
            [
                SimpleNamespace(used=90, total=100, free=10),
                SimpleNamespace(used=95, total=100, free=5),
                SimpleNamespace(used=70, total=100, free=30),
                SimpleNamespace(used=90, total=100, free=10),
            ]
        )

        for _ in range(4):
            check_disk_once(
                ["/data"], alerted, 80, messages.append, metrics, lambda _: next(usages)
            )

        self.assertEqual(len(messages), 2)
        self.assertEqual(metrics.snapshot()["disk_check_failures"], 0)

    def test_rate_limit_records_dropped_alert(self):
        metrics = Metrics()
        limiter = AlertRateLimiter(1, clock=lambda: 10)
        sent = []
        notifier = TelegramNotifier(
            "token",
            "chat",
            metrics=metrics,
            limiter=limiter,
            post=lambda *args, **kwargs: sent.append(kwargs) or Response(),
        )

        self.assertTrue(notifier.send("first"))
        self.assertFalse(notifier.send("second"))
        self.assertEqual(len(sent), 1)
        self.assertEqual(metrics.snapshot()["alerts_dropped"], 1)

    def test_transport_failure_records_failed_alert(self):
        metrics = Metrics()
        notifier = TelegramNotifier(
            "token",
            "chat",
            metrics=metrics,
            post=lambda *args, **kwargs: Response(ValueError("telegram unavailable")),
        )
        self.assertFalse(notifier.send("message"))
        self.assertEqual(metrics.snapshot()["alerts_failed"], 1)

    def test_oversized_message_is_bounded(self):
        captured = []
        notifier = TelegramNotifier(
            "token",
            "chat",
            post=lambda *args, **kwargs: captured.append(kwargs["json"]["text"]) or Response(),
        )
        self.assertTrue(notifier.send("<b>" + ("x" * 5000)))
        self.assertLessEqual(len(captured[0]), 4096)
        self.assertIn("&lt;b&gt;", captured[0])

    def test_backoff_is_exponential_and_jittered(self):
        self.assertEqual(reconnect_delay(0, 1, 60, 0.2, lambda: 0), 1)
        self.assertEqual(reconnect_delay(2, 1, 60, 0.2, lambda: 0.5), 4.4)
        self.assertEqual(reconnect_delay(10, 1, 5, 0.2, lambda: 1), 5)

    def test_config_reads_new_operational_controls(self):
        config = Config.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_CHAT_ID": "chat",
                "WATCHER_ALERTS_PER_MINUTE": "12",
                "RECONNECT_INITIAL_DELAY": "2",
                "RECONNECT_MAX_DELAY": "10",
                "RECONNECT_JITTER": "0.1",
            }
        )
        self.assertEqual(config.alert_rate_limit, 12)
        self.assertEqual(config.reconnect_initial_delay, 2)
        self.assertEqual(config.reconnect_max_delay, 10)
        self.assertEqual(config.reconnect_jitter, 0.1)


if __name__ == "__main__":
    unittest.main()
