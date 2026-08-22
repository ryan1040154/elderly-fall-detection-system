from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CameraConfig:
    source: int | str = 0
    width: int = 1280
    height: int = 720
    inference_fps: float = 10.0


@dataclass
class ModelConfig:
    name: str = "yolo11n-pose.pt"
    confidence: float = 0.45
    device: str = ""
    tracker: str = "bytetrack.yaml"


@dataclass
class DetectionConfig:
    confirmation_seconds: float = 1.5
    alert_after_seconds: float = 30.0
    recovery_seconds: float = 1.5
    missing_person_grace_seconds: float = 2.0
    horizontal_angle_degrees: float = 55.0
    bbox_aspect_ratio: float = 1.05
    rapid_drop_per_second: float = 0.35
    min_keypoint_confidence: float = 0.35


@dataclass
class RecordingConfig:
    enabled: bool = True
    output_directory: str = "events"
    seconds_before: float = 10.0
    seconds_after: float = 20.0


@dataclass
class NotificationConfig:
    line_enabled: bool = False
    line_target: str = "single"
    line_channel_access_token: str = ""
    line_user_id: str = ""
    bark_enabled: bool = False
    bark_server: str = "https://api.day.app"
    bark_device_keys: list[str] = field(default_factory=list)
    bark_level: str = "critical"
    bark_volume: int = 10
    bark_sound: str = "electronic"
    bark_call: bool = True


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    fall_detection: DetectionConfig = field(default_factory=DetectionConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{name}' must be a mapping")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing {config_path}. Copy config.example.yaml to config.yaml first."
        )
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    camera_data = _section(data, "camera")
    source = camera_data.get("source", 0)
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    camera_data["source"] = source
    config = AppConfig(
        camera=CameraConfig(**camera_data),
        model=ModelConfig(**_section(data, "model")),
        fall_detection=DetectionConfig(**_section(data, "fall_detection")),
        recording=RecordingConfig(**_section(data, "recording")),
        notification=NotificationConfig(**_section(data, "notification")),
    )
    if config.notification.line_target not in {"single", "broadcast"}:
        raise ValueError("notification.line_target must be 'single' or 'broadcast'")
    if (
        config.notification.line_enabled
        and config.notification.line_target == "single"
        and not config.notification.line_user_id
    ):
        raise ValueError("notification.line_user_id is required when line_target is 'single'")
    if config.notification.bark_level not in {"critical", "active", "timeSensitive", "passive"}:
        raise ValueError(
            "notification.bark_level must be critical, active, timeSensitive, or passive"
        )
    if not 0 <= config.notification.bark_volume <= 10:
        raise ValueError("notification.bark_volume must be between 0 and 10")
    if config.notification.bark_enabled and not config.notification.bark_device_keys:
        raise ValueError("notification.bark_device_keys is required when Bark is enabled")
    return config
