import datetime
import unittest

from presence.telemetry import (
    format_duration,
    old_usage_filenames,
    update_usage_record,
    usage_payload,
    with_age,
)


class PresenceTelemetryTests(unittest.TestCase):
    def test_with_age_adds_age_and_optional_stale_flag_without_mutating_input(self):
        data = {"ts": 100.5, "status": "ok"}

        result = with_age(data, now=135.9, stale_after=30)

        self.assertEqual(result, {"ts": 100.5, "status": "ok", "age_seconds": 35, "stale": True})
        self.assertEqual(data, {"ts": 100.5, "status": "ok"})
        self.assertIsNone(with_age(None, now=1))

    def test_with_age_omits_stale_flag_when_threshold_is_none(self):
        self.assertEqual(with_age({"ts": 10}, now=15), {"ts": 10, "age_seconds": 5})

    def test_format_duration(self):
        self.assertEqual(format_duration(59), "0m")
        self.assertEqual(format_duration(61), "1m")
        self.assertEqual(format_duration(3661), "1h01m")

    def test_usage_payload_formats_sorted_apps(self):
        usage = {
            "date": "2026-07-01",
            "apps": {
                "b": {"label": "B", "seconds": 60},
                "a": {"label": "A", "seconds": 3660},
            },
        }

        self.assertEqual(
            usage_payload(usage, date="fallback"),
            {
                "date": "2026-07-01",
                "total": "1h02m",
                "total_seconds": 3720,
                "apps": [
                    {"app": "a", "label": "A", "time": "1h01m", "seconds": 3660},
                    {"app": "b", "label": "B", "time": "1m", "seconds": 60},
                ],
            },
        )

    def test_usage_payload_handles_empty_usage(self):
        self.assertEqual(usage_payload(None, date="2026-07-01"), {"status": "no data yet", "date": "2026-07-01"})
        self.assertEqual(usage_payload({"apps": {}}, date="2026-07-01"), {"status": "no data yet", "date": "2026-07-01"})

    def test_update_usage_record_adds_and_updates_apps_without_mutating_input(self):
        usage = {"date": "2026-07-01", "apps": {"pkg": {"label": "Old", "seconds": 10}}}

        result = update_usage_record(usage, app="pkg", label="New", seconds=5, date="2026-07-01", now=123)

        self.assertEqual(result["apps"]["pkg"], {"label": "New", "seconds": 15})
        self.assertEqual(result["last_updated"], 123)
        self.assertEqual(usage["apps"]["pkg"], {"label": "Old", "seconds": 10})

    def test_update_usage_record_resets_on_new_date(self):
        result = update_usage_record(
            {"date": "2026-06-30", "apps": {"old": {"label": "Old", "seconds": 10}}},
            app="pkg",
            label="",
            seconds=5,
            date="2026-07-01",
            now=123,
        )

        self.assertEqual(result["date"], "2026-07-01")
        self.assertEqual(result["apps"], {"pkg": {"label": "pkg", "seconds": 5}})

    def test_old_usage_filenames_returns_only_old_dated_json(self):
        now = datetime.datetime(2026, 7, 10, 12, 0, 0)

        self.assertEqual(
            old_usage_filenames(
                ["2026-07-05.json", "2026-07-08.json", "bad.json", "2026-07-01.txt"],
                now=now,
                keep_days=3,
            ),
            ["2026-07-05.json"],
        )


if __name__ == "__main__":
    unittest.main()
