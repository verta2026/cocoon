import unittest

from presence.push_subscriptions import (
    missing_vapid_record,
    push_delivery_record,
    push_status_payload,
    remove_subscription,
    upsert_subscription,
)


class PresencePushSubscriptionsTests(unittest.TestCase):
    def test_push_status_payload_uses_public_key_presence_only(self):
        last = {"sent": 1}

        self.assertEqual(
            push_status_payload(public_key="public", subscriptions=[{"endpoint": "a"}], last=last),
            {"vapid": True, "subscriptions": 1, "last": last},
        )
        self.assertEqual(
            push_status_payload(public_key=None, subscriptions=[], last=None),
            {"vapid": False, "subscriptions": 0, "last": None},
        )

    def test_upsert_subscription_inserts_timestamps_without_mutating_input(self):
        subscription = {"endpoint": "a", "keys": {"p256dh": "k"}}

        result = upsert_subscription([], subscription, now=12.5)

        self.assertEqual(result[0]["endpoint"], "a")
        self.assertEqual(result[0]["created_at"], 12.5)
        self.assertEqual(result[0]["updated_at"], 12.5)
        self.assertNotIn("created_at", subscription)

    def test_upsert_subscription_updates_existing_and_preserves_created_at(self):
        existing = [{"endpoint": "a", "created_at": 1.0, "updated_at": 2.0, "old": True}]

        result = upsert_subscription(existing, {"endpoint": "a", "new": True}, now=3.0)

        self.assertEqual(result, [{"endpoint": "a", "new": True, "updated_at": 3.0, "created_at": 1.0}])
        self.assertEqual(existing[0]["old"], True)

    def test_upsert_subscription_rejects_missing_endpoint(self):
        with self.assertRaises(ValueError):
            upsert_subscription([], {}, now=1.0)

    def test_remove_subscription_filters_by_endpoint_without_mutating_input(self):
        subscriptions = [{"endpoint": "a"}, {"endpoint": "b"}]

        self.assertEqual(remove_subscription(subscriptions, "a"), [{"endpoint": "b"}])
        self.assertEqual(subscriptions, [{"endpoint": "a"}, {"endpoint": "b"}])

    def test_remove_subscription_rejects_missing_endpoint(self):
        with self.assertRaises(ValueError):
            remove_subscription([], "")

    def test_missing_vapid_record(self):
        self.assertEqual(
            missing_vapid_record(now=2.0, attempted=4),
            {"ts": 2.0, "attempted": 4, "sent": 0, "error": "missing vapid"},
        )

    def test_push_delivery_record_keeps_latest_errors(self):
        self.assertEqual(
            push_delivery_record(
                now=5.0,
                attempted=10,
                sent=3,
                kept=7,
                errors=["a", "b", "c"],
                max_errors=2,
            ),
            {"ts": 5.0, "attempted": 10, "sent": 3, "kept": 7, "errors": ["b", "c"]},
        )


if __name__ == "__main__":
    unittest.main()
