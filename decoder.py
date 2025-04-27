import subprocess
import numpy as np

class FFmpegDecoder:
    """Decodes H264 buffers to raw BGR frames."""
    def __init__(self):
        args = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-i", "pipe:0",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        ]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

    def feed(self, data: bytes):
        if self.process.stdin:
            try:
                self.process.stdin.write(data)
            except (BrokenPipeError, ValueError):
                # ignore broken pipe or write on closed stdin
                pass

    def frames(self, width: int, height: int):
        bytes_per_frame = width * height * 3
        buffer = bytearray()
        while True:
            chunk = self.process.stdout.read(4096)
            if not chunk:
                if self.process.poll() is not None:
                    return
                continue
            buffer.extend(chunk)
            while len(buffer) >= bytes_per_frame:
                frame_data = buffer[:bytes_per_frame]
                del buffer[:bytes_per_frame]
                frame = np.frombuffer(frame_data, np.uint8).reshape((height, width, 3))
                yield frame

    def close(self):
        try:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass