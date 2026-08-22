from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .config import RecordingConfig


class EventRecorder:
    def __init__(self, config: RecordingConfig, fps: float):
        self.config = config
        self.fps = max(1.0, fps)
        self.buffer: deque[np.ndarray] = deque(maxlen=max(1, int(config.seconds_before * self.fps)))
        self.writer: cv2.VideoWriter | None = None
        self.remaining_frames = 0
        self.current_path: Path | None = None

    def add_frame(self, frame: np.ndarray) -> None:
        if not self.config.enabled:
            return
        self.buffer.append(frame.copy())
        if self.writer is not None:
            self.writer.write(frame)
            self.remaining_frames -= 1
            if self.remaining_frames <= 0:
                self.close()

    def trigger(self, frame_size: tuple[int, int]) -> Path | None:
        if not self.config.enabled:
            return None
        if self.writer is not None:
            self.remaining_frames = max(
                self.remaining_frames, int(self.config.seconds_after * self.fps)
            )
            return self.current_path

        output_dir = Path(self.config.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_path = output_dir / f"fall_{timestamp}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(str(self.current_path), fourcc, self.fps, frame_size)
        if not self.writer.isOpened():
            self.writer = None
            self.current_path = None
            return None
        for buffered_frame in self.buffer:
            self.writer.write(buffered_frame)
        self.remaining_frames = int(self.config.seconds_after * self.fps)
        return self.current_path

    def close(self) -> None:
        if self.writer is not None:
            self.writer.release()
        self.writer = None
        self.remaining_frames = 0

