import unittest
from unittest.mock import Mock, patch

from fall_detection.config import NotificationConfig
from fall_detection.notifier import BarkNotifier, LineNotifier


class LineNotifierTests(unittest.TestCase):
    @patch("fall_detection.notifier.requests.post")
    def test_single_target_uses_push_endpoint_and_user_id(self, post):
        post.return_value = Mock(ok=True)
        notifier = LineNotifier(NotificationConfig(True, "single", "token", "user-id"))

        self.assertTrue(notifier.send_alert(1))
        args, kwargs = post.call_args
        self.assertEqual(args[0], LineNotifier.PUSH_ENDPOINT)
        self.assertEqual(kwargs["json"]["to"], "user-id")

    @patch("fall_detection.notifier.requests.post")
    def test_broadcast_uses_broadcast_endpoint_without_user_id(self, post):
        post.return_value = Mock(ok=True)
        notifier = LineNotifier(NotificationConfig(True, "broadcast", "token", ""))

        self.assertTrue(notifier.send_alert(1))
        args, kwargs = post.call_args
        self.assertEqual(args[0], LineNotifier.BROADCAST_ENDPOINT)
        self.assertNotIn("to", kwargs["json"])


class BarkNotifierTests(unittest.TestCase):
    @patch("fall_detection.notifier.requests.post")
    def test_critical_call_alert_to_multiple_devices(self, post):
        post.return_value = Mock(ok=True)
        config = NotificationConfig(
            bark_enabled=True,
            bark_device_keys=["device-a", "device-b"],
            bark_level="critical",
            bark_volume=10,
            bark_sound="electronic",
            bark_call=True,
        )

        self.assertTrue(BarkNotifier(config).send_alert(7))
        self.assertEqual(post.call_count, 2)
        args, kwargs = post.call_args_list[0]
        self.assertEqual(args[0], "https://api.day.app/push")
        self.assertEqual(kwargs["json"]["device_key"], "device-a")
        self.assertEqual(kwargs["json"]["level"], "critical")
        self.assertEqual(kwargs["json"]["call"], "1")


if __name__ == "__main__":
    unittest.main()
