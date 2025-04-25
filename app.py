import time
import cv2

from swimmer_detector import SwimmerDetector
from swim_lap_counter.config import (
    WEBSOCKET_URL,
    DEVICE_SERIAL_NUMBER,
    CONFIDENCE_THRESHOLD,
    PROCESS_EVERY_N_FRAMES,
    START_ZONE,
    END_ZONE,
)
from swim_lap_counter.client import EufyClient
from swim_lap_counter.decoder import FFmpegDecoder
from swim_lap_counter.recorder import VideoRecorder

class SwimApp:
    """Main application orchestrator."""
    def __init__(self):
        self.client = EufyClient(WEBSOCKET_URL, DEVICE_SERIAL_NUMBER)
        self.decoder = FFmpegDecoder()
        self.detector = SwimmerDetector(
            START_ZONE,
            END_ZONE,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            process_every_n_frames=PROCESS_EVERY_N_FRAMES,
        )
        self.recorder = None

    def run(self):
        self.client.connect()
        first_data, info = self.client.start_livestream()
        width, height, fps = info["width"], info["height"], info["fps"]
        print(f"Stream metadata: {width}×{height} @ {fps} FPS")
        self.decoder.feed(first_data)
        self.client.listen(self.decoder.feed)
        out_file = f"record_{int(time.time())}.mp4"
        print(f"Recording output to: {out_file}")
        self.recorder = VideoRecorder(out_file, fps, (width, height))
        print("Entering main loop. Press Ctrl-C or 'q' to exit.")
        try:
            for frame in self.decoder.frames(width, height):
                out = self.detector.process(frame)
                cv2.putText(
                    out,
                    f"Laps: {self.detector.lap_count}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                self.recorder.write(out)
                self.recorder.display(out)
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        print("Stopping livestream and cleaning up...")
        self.decoder.close()
        self.client.close()
        if self.recorder:
            self.recorder.close()
        print(f"Total laps counted: {self.detector.lap_count}")

def main():
    app = SwimApp()
    app.run()

if __name__ == "__main__":
    main()