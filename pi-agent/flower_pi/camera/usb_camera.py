from pathlib import Path
import subprocess


class USBCamera:
    def __init__(
        self, path, max_bytes=10 * 1024 * 1024, warmup_frames=5, min_brightness=25, min_sharpness=40
    ):
        if not str(path).startswith("/dev/v4l/by-id/"):
            raise ValueError("use a stable /dev/v4l/by-id camera path")
        self.path = str(path)
        self.max_bytes, self.warmup_frames = max_bytes, warmup_frames
        self.min_brightness, self.min_sharpness = min_brightness, min_sharpness

    def capture(self):
        # Isolate native camera calls: a stuck driver must not stall the safety loop.
        result = subprocess.run(
            [
                "python3",
                "-m",
                "flower_pi.camera.usb_camera",
                self.path,
                str(self.warmup_frames),
                str(self.min_brightness),
                str(self.min_sharpness),
            ],
            capture_output=True,
            timeout=20,
        )
        if result.returncode or not result.stdout or len(result.stdout) > self.max_bytes:
            raise ValueError("CAMERA_QUALITY_FAILED")
        return result.stdout


def main():
    import sys
    import cv2

    path, warmup, brightness, sharpness = sys.argv[1:]
    if not Path(path).exists():
        raise ValueError("CAMERA_UNAVAILABLE")
    capture = cv2.VideoCapture(path, cv2.CAP_V4L2)
    try:
        for _ in range(int(warmup) + 1):
            ok, frame = capture.read()
            if not ok:
                raise ValueError("CAMERA_UNAVAILABLE")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if gray.mean() < float(brightness) or cv2.Laplacian(gray, cv2.CV_64F).var() < float(
            sharpness
        ):
            raise ValueError("CAMERA_QUALITY_FAILED")
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("CAMERA_ENCODING_FAILED")
        sys.stdout.buffer.write(encoded.tobytes())
    finally:
        capture.release()


if __name__ == "__main__":
    main()
