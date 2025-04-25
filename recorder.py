import cv2
import numpy as np

class VideoRecorder:
    """Handles video writing and display."""
    def __init__(self, filename: str, fps: float, size: tuple[int, int], window_name: str = "SwimCam"):
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(filename, fourcc, fps, size)
        self.window_name = window_name

    def write(self, frame: np.ndarray):
        self.writer.write(frame)

    def display(self, frame: np.ndarray):
        cv2.imshow(self.window_name, frame)

    def close(self):
        try:
            self.writer.release()
        except Exception:
            pass
        cv2.destroyAllWindows()