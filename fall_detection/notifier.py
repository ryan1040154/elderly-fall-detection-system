from __future__ import annotations

import logging
from pathlib import Path

import requests

from .config import NotificationConfig

LOGGER = logging.getLogger(__name__)


class LineNotifier:
    PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
    BROADCAST_ENDPOINT = "https://api.line.me/v2/bot/message/broadcast"

    def __init__(self, config: NotificationConfig):
        self.config = config

    def send_alert(self, person_id: int, event_path: Path | None = None) -> bool:
        if not self.config.line_enabled:
            LOGGER.info("LINE notification disabled; alert for person %s", person_id)
            return False
        if not self.config.line_channel_access_token:
            LOGGER.error("LINE is enabled but channel access token is missing")
            return False
        if self.config.line_target == "single" and not self.config.line_user_id:
            LOGGER.error("LINE single target requires a user ID")
            return False

        message = f"長輩疑似跌倒超過30秒未起身，請立刻確認！偵測到人物 {person_id} 請立即確認。"
        if event_path:
            message += f"\n本機事件檔案：{event_path.name}"
        payload = {"messages": [{"type": "text", "text": message}]}
        endpoint = self.BROADCAST_ENDPOINT
        if self.config.line_target == "single":
            endpoint = self.PUSH_ENDPOINT
            payload["to"] = self.config.line_user_id

        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {self.config.line_channel_access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if response.ok:
            return True
        LOGGER.error("LINE notification failed: %s %s", response.status_code, response.text)
        return False


class BarkNotifier:
    """Send urgent iOS notifications through a Bark-compatible server."""

    def __init__(self, config: NotificationConfig):
        self.config = config

    def send_alert(self, person_id: int, event_path: Path | None = None) -> bool:
        if not self.config.bark_enabled:
            LOGGER.info("Bark notification disabled; alert for person %s", person_id)
            return False
        payload: dict[str, object] = {
            "title": "跌倒警報！",
            "body": f"長輩疑似跌倒超過30秒未起身，請立刻確認！",
            "level": self.config.bark_level,
            "volume": self.config.bark_volume,
            "sound": self.config.bark_sound,
            "group": "fall-detection",
        }
        if self.config.bark_call:
            payload["call"] = "1"
        if event_path:
            payload["body"] = f"{payload['body']} 本機事件：{event_path.name}"

        endpoint = f"{self.config.bark_server.rstrip('/')}/push"
        all_succeeded = True
        for device_key in self.config.bark_device_keys:
            device_payload = {**payload, "device_key": device_key}
            try:
                response = requests.post(endpoint, json=device_payload, timeout=10)
            except requests.RequestException as error:
                LOGGER.error("Bark notification request failed: %s", error)
                all_succeeded = False
                continue
            if not response.ok:
                LOGGER.error("Bark notification failed: %s %s", response.status_code, response.text)
                all_succeeded = False
        return all_succeeded


def sound_alarm() -> None:
    try:
        import winsound

        winsound.Beep(1200, 800)
        winsound.Beep(900, 800)
    except (ImportError, RuntimeError):
        print("\a", end="", flush=True)
