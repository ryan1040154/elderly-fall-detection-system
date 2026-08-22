from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees

import numpy as np

from .config import DetectionConfig


class FallState(str, Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    ON_GROUND = "on_ground"
    ALERTED = "alerted"


class FallEvent(str, Enum):
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    ALERT = "alert"
    RECOVERED = "recovered"
    CANCELLED = "cancelled"


@dataclass
class PoseObservation:
    person_id: int
    timestamp: float
    keypoints: np.ndarray  # shape (17, 3): x, y, confidence
    bbox: tuple[float, float, float, float]
    frame_width: int
    frame_height: int


@dataclass
class PoseMetrics:
    horizontal: bool
    torso_angle: float
    bbox_aspect_ratio: float
    hip_y_normalized: float | None
    rapid_drop: bool
    enough_keypoints: bool


@dataclass
class TrackState:
    state: FallState = FallState.NORMAL
    state_since: float = 0.0
    last_seen: float = 0.0
    previous_hip_y: float | None = None
    previous_timestamp: float | None = None
    recovery_since: float | None = None


@dataclass
class DetectionResult:
    person_id: int
    state: FallState
    event: FallEvent
    elapsed: float
    metrics: PoseMetrics


def _mean_point(keypoints: np.ndarray, indices: tuple[int, ...], min_conf: float):
    points = [keypoints[i, :2] for i in indices if keypoints[i, 2] >= min_conf]
    return np.mean(points, axis=0) if points else None


class FallDetector:
    """Rule-based temporal fall detector operating on tracked pose observations."""

    def __init__(self, config: DetectionConfig):
        self.config = config
        self.tracks: dict[int, TrackState] = {}

    def _metrics(self, observation: PoseObservation, track: TrackState) -> PoseMetrics:
        k = observation.keypoints
        conf = self.config.min_keypoint_confidence
        shoulders = _mean_point(k, (5, 6), conf)
        hips = _mean_point(k, (11, 12), conf)
        enough = shoulders is not None and hips is not None

        angle = 0.0
        hip_y = None
        rapid_drop = False
        if enough:
            dx = float(hips[0] - shoulders[0])
            dy = float(hips[1] - shoulders[1])
            angle = degrees(atan2(abs(dx), max(abs(dy), 1e-6)))
            hip_y = float(hips[1] / observation.frame_height)
            if track.previous_hip_y is not None and track.previous_timestamp is not None:
                dt = observation.timestamp - track.previous_timestamp
                if 0 < dt <= 2.0:
                    rapid_drop = (
                        (hip_y - track.previous_hip_y) / dt
                        >= self.config.rapid_drop_per_second
                    )

        x1, y1, x2, y2 = observation.bbox
        width = max(x2 - x1, 1.0)
        height = max(y2 - y1, 1.0)
        ratio = width / height
        horizontal = enough and (
            angle >= self.config.horizontal_angle_degrees
            or ratio >= self.config.bbox_aspect_ratio
        )
        return PoseMetrics(horizontal, angle, ratio, hip_y, rapid_drop, enough)

    def update(self, observation: PoseObservation) -> DetectionResult:
        now = observation.timestamp
        track = self.tracks.setdefault(
            observation.person_id, TrackState(state_since=now, last_seen=now)
        )
        metrics = self._metrics(observation, track)
        event = FallEvent.NONE
        track.last_seen = now

        if track.state == FallState.NORMAL:
            # Rapid downward motion strengthens the evidence but horizontal posture
            # alone starts confirmation so falls between sampled frames are not lost.
            if metrics.horizontal:
                track.state = FallState.SUSPECTED
                track.state_since = now
                event = FallEvent.SUSPECTED

        elif track.state == FallState.SUSPECTED:
            if not metrics.horizontal:
                track.state = FallState.NORMAL
                track.state_since = now
            elif now - track.state_since >= self.config.confirmation_seconds:
                track.state = FallState.ON_GROUND
                track.state_since = now
                event = FallEvent.CONFIRMED

        elif track.state in (FallState.ON_GROUND, FallState.ALERTED):
            if metrics.horizontal:
                track.recovery_since = None
                if (
                    track.state == FallState.ON_GROUND
                    and now - track.state_since >= self.config.alert_after_seconds
                ):
                    track.state = FallState.ALERTED
                    event = FallEvent.ALERT
            else:
                track.recovery_since = track.recovery_since or now
                if now - track.recovery_since >= self.config.recovery_seconds:
                    track.state = FallState.NORMAL
                    track.state_since = now
                    track.recovery_since = None
                    event = FallEvent.RECOVERED

        if metrics.hip_y_normalized is not None:
            track.previous_hip_y = metrics.hip_y_normalized
            track.previous_timestamp = now

        return DetectionResult(
            observation.person_id,
            track.state,
            event,
            max(0.0, now - track.state_since),
            metrics,
        )

    def cancel(self, now: float) -> list[int]:
        cancelled = []
        for person_id, track in self.tracks.items():
            if track.state != FallState.NORMAL:
                cancelled.append(person_id)
                track.state = FallState.NORMAL
                track.state_since = now
                track.recovery_since = None
        return cancelled

    def expire_missing(self, now: float) -> None:
        grace = self.config.missing_person_grace_seconds
        stale = [
            person_id
            for person_id, track in self.tracks.items()
            if now - track.last_seen > grace and track.state in (FallState.NORMAL, FallState.SUSPECTED)
        ]
        for person_id in stale:
            del self.tracks[person_id]

