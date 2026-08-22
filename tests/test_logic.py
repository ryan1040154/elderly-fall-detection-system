import unittest

import numpy as np

from fall_detection.config import DetectionConfig
from fall_detection.logic import FallDetector, FallEvent, FallState, PoseObservation


def pose(timestamp: float, horizontal: bool, person_id: int = 1) -> PoseObservation:
    keypoints = np.zeros((17, 3), dtype=np.float32)
    if horizontal:
        keypoints[5] = [200, 300, 1]
        keypoints[6] = [200, 320, 1]
        keypoints[11] = [400, 300, 1]
        keypoints[12] = [400, 320, 1]
        bbox = (150, 250, 500, 380)
    else:
        keypoints[5] = [300, 150, 1]
        keypoints[6] = [330, 150, 1]
        keypoints[11] = [300, 350, 1]
        keypoints[12] = [330, 350, 1]
        bbox = (250, 100, 380, 650)
    return PoseObservation(person_id, timestamp, keypoints, bbox, 1280, 720)


class FallDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = FallDetector(
            DetectionConfig(confirmation_seconds=1, alert_after_seconds=3, recovery_seconds=1)
        )

    def test_sustained_horizontal_pose_alerts_once(self):
        self.assertEqual(self.detector.update(pose(0, True)).event, FallEvent.SUSPECTED)
        confirmed = self.detector.update(pose(1.1, True))
        self.assertEqual(confirmed.event, FallEvent.CONFIRMED)
        self.assertEqual(confirmed.state, FallState.ON_GROUND)
        self.assertEqual(self.detector.update(pose(3.9, True)).event, FallEvent.NONE)
        alert = self.detector.update(pose(4.2, True))
        self.assertEqual(alert.event, FallEvent.ALERT)
        self.assertEqual(self.detector.update(pose(5, True)).event, FallEvent.NONE)

    def test_short_horizontal_pose_does_not_confirm(self):
        self.detector.update(pose(0, True))
        result = self.detector.update(pose(0.5, False))
        self.assertEqual(result.state, FallState.NORMAL)

    def test_recovery_and_cancel(self):
        self.detector.update(pose(0, True))
        self.detector.update(pose(1.1, True))
        self.detector.update(pose(1.5, False))
        result = self.detector.update(pose(2.6, False))
        self.assertEqual(result.event, FallEvent.RECOVERED)
        self.detector.update(pose(3, True))
        self.assertEqual(self.detector.cancel(3.1), [1])
        self.assertEqual(self.detector.tracks[1].state, FallState.NORMAL)


if __name__ == "__main__":
    unittest.main()

