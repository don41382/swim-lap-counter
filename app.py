import time
import threading
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import cv2
import logging

# configure logging for the application
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

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
        # Streams and components will be instantiated on start()
        self.client = None
        self.decoder = None
        self.detector = None
        self.recorder = None
        # Control flags and thread
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None

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
        # Initialize idle shutdown timer: shutdown if no lap detected within 5 minutes
        last_lap_time = time.time()
        previous_lap_count = self.detector.lap_count
        try:
            for frame in self.decoder.frames(width, height):
                out = self.detector.process(frame)
                # Check for new laps to reset idle timer
                if self.detector.lap_count > previous_lap_count:
                    previous_lap_count = self.detector.lap_count
                    last_lap_time = time.time()
                # Shutdown if idle for more than 5 minutes
                elif time.time() - last_lap_time > 5 * 60:
                    print("No laps detected in the last 5 minutes, shutting down.")
                    break
                cv2.putText(
                    out,
                    f"Laps: {self.detector.lap_count}",
                    (300, 400),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2.0,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                self.recorder.write(out)
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
    # Web control API methods
    def _stream_loop(self):
        # Initialize and start livestream
        try:
            self.client.connect()
            first_data, info = self.client.start_livestream()
            width, height, fps = info["width"], info["height"], info["fps"]
            print(f"Stream metadata: {width}×{height} @ {fps} FPS")
            self.decoder.feed(first_data)
            self.client.listen(self.decoder.feed)
            out_file = f"record_{int(time.time())}.mp4"
            print(f"Recording output to: {out_file}")
            self.recorder = VideoRecorder(out_file, fps, (width, height))
            print("Streaming started. Use /stop endpoint or 'q'/Ctrl-C to stop.")

            # Idle timeout: shutdown if no new laps within 5 minutes
            last_lap_time = time.time()
            previous_lap_count = self.detector.lap_count
            for frame in self.decoder.frames(width, height):
                if self._stop_event.is_set():
                    break
                out = self.detector.process(frame)
                # Reset idle timer on new lap
                if self.detector.lap_count > previous_lap_count:
                    previous_lap_count = self.detector.lap_count
                    last_lap_time = time.time()
                # Idle shutdown
                elif time.time() - last_lap_time > 5 * 60:
                    print("No laps detected in the last 5 minutes, shutting down.")
                    break
                cv2.putText(
                    out,
                    f"Laps: {self.detector.lap_count}",
                    (300, 400),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2.0,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                self.recorder.write(out)
        except Exception:
            logging.exception("Error in stream loop")
        finally:
            self.shutdown()
            self._running = False

    def start(self) -> bool:
        """Start the swim lap counting stream; returns False if already running."""
        if self._running:
            return False
        # Prepare components
        self.client = EufyClient(WEBSOCKET_URL, DEVICE_SERIAL_NUMBER)
        self.decoder = FFmpegDecoder()
        self.detector = SwimmerDetector(
            START_ZONE,
            END_ZONE,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            process_every_n_frames=PROCESS_EVERY_N_FRAMES,
        )
        self.recorder = None
        self._stop_event.clear()
        # Launch streaming thread
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._running = True
        self._thread.start()
        return True

    def stop(self) -> bool:
        """Signal the stream to stop; returns False if not running."""
        if not self._running:
            return False
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        return True

    def status(self) -> dict:
        """Return current running state and lap count."""
        laps = self.detector.lap_count if self.detector else 0
        return {"running": self._running, "laps": laps}

def main():
    app = SwimApp()
    # HTTP server for control API
    class RequestHandler(BaseHTTPRequestHandler):
        def _set_headers(self, code=200, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/status":
                status = app.status()
                self._set_headers()
                self.wfile.write(json.dumps(status).encode())
            elif path == "/start":
                if app.start():
                    self._set_headers()
                    self.wfile.write(json.dumps({"status": "started"}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "already running"}).encode())
            elif path == "/stop":
                if app.stop():
                    self._set_headers()
                    self.wfile.write(json.dumps({"status": "stopped"}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "not running"}).encode())
            else:
                self.send_error(404, "Not Found")

    server = ThreadingHTTPServer(("0.0.0.0", 8080), RequestHandler)
    print("Starting HTTP server on port 8080...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.exception("HTTP server error")
    finally:
        if app._running:
            app.stop()
        server.server_close()

if __name__ == "__main__":
    main()