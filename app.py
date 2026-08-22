from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

# Keep Ultralytics runtime settings inside the project. This avoids failures on
# locked-down Windows accounts and makes edge-device deployments self-contained.
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(__file__).resolve().parent / ".ultralytics"))

import cv2
import numpy as np
from ultralytics import YOLO

from fall_detection.config import load_config
from fall_detection.logic import FallDetector, FallEvent, FallState, PoseObservation
from fall_detection.notifier import BarkNotifier, LineNotifier, sound_alarm
from fall_detection.recorder import EventRecorder

LOGGER = logging.getLogger("fall-detection")

STATE_COLORS = {
    FallState.NORMAL: (40, 200, 40),
    FallState.SUSPECTED: (0, 200, 255),
    FallState.ON_GROUND: (0, 120, 255),
    FallState.ALERTED: (0, 0, 255),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO Pose elderly fall-detection MVP")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-display", action="store_true", help="Run without a preview window")
    return parser.parse_args()


def keypoints_with_confidence(result, index: int) -> np.ndarray:
    xy = result.keypoints.xy[index].cpu().numpy()
    if result.keypoints.conf is None:
        conf = np.ones((xy.shape[0], 1), dtype=np.float32)
    else:
        conf = result.keypoints.conf[index].cpu().numpy().reshape(-1, 1)
    return np.concatenate((xy, conf), axis=1)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    model = YOLO(config.model.name)
    capture = cv2.VideoCapture(config.camera.source)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open camera/video source: {config.camera.source}")

    detector = FallDetector(config.fall_detection)
    notifier = LineNotifier(config.notification)
    bark_notifier = BarkNotifier(config.notification)
    recorder = EventRecorder(config.recording, config.camera.inference_fps)
    min_interval = 1.0 / max(config.camera.inference_fps, 1.0)
    last_inference = 0.0
    last_results = []

    LOGGER.info("Started. Press C to cancel an alarm, Q to quit.")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                LOGGER.info("Video stream ended")
                break
            now = time.monotonic()
            display = frame.copy()

            if now - last_inference >= min_interval:
                kwargs = {
                    "source": frame,
                    "persist": True,
                    "tracker": config.model.tracker,
                    "conf": config.model.confidence,
                    "verbose": False,
                }
                if config.model.device:
                    kwargs["device"] = config.model.device
                prediction = model.track(**kwargs)[0]
                last_inference = now
                last_results = []

                if prediction.boxes is not None and prediction.keypoints is not None:
                    boxes = prediction.boxes.xyxy.cpu().numpy()
                    ids = prediction.boxes.id
                    track_ids = (
                        ids.int().cpu().tolist() if ids is not None else list(range(len(boxes)))
                    )
                    height, width = frame.shape[:2]
                    for index, (box, person_id) in enumerate(zip(boxes, track_ids)):
                        observation = PoseObservation(
                            int(person_id), now, keypoints_with_confidence(prediction, index),
                            tuple(float(v) for v in box), width, height,
                        )
                        result = detector.update(observation)
                        last_results.append((box, result))
                        if result.event == FallEvent.CONFIRMED:
                            LOGGER.warning("Fall confirmed for person %s", result.person_id)
                        elif result.event == FallEvent.ALERT:
                            event_path = recorder.trigger((width, height))
                            LOGGER.error("Fall alert for person %s", result.person_id)
                            sound_alarm()
                            notifier.send_alert(result.person_id, event_path)
                            bark_notifier.send_alert(result.person_id, event_path)
                detector.expire_missing(now)

            for box, result in last_results:
                x1, y1, x2, y2 = (int(value) for value in box)
                color = STATE_COLORS[result.state]
                cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                remaining = max(0.0, config.fall_detection.alert_after_seconds - result.elapsed)
                label = f"ID {result.person_id}: {result.state.value}"
                if result.state == FallState.ON_GROUND:
                    label += f" alert in {remaining:.0f}s"
                cv2.putText(display, label, (x1, max(25, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

            cv2.putText(display, "C: cancel  Q: quit", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            recorder.add_frame(display)

            if not args.no_display:
                cv2.imshow("Fall Detection MVP", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("c"):
                    cancelled = detector.cancel(time.monotonic())
                    LOGGER.info("Cancelled alerts for IDs: %s", cancelled)
    finally:
        recorder.close()
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
