"""
Live MJPEG stream with classic-CV pen detection overlay (validation aid).

DepthAI v3, 640x360 @ 15fps (USB2-safe). Detects an elongated object (the pen)
inside a mat ROI using flat-field background subtraction + elongation filtering,
and overlays the ROI (cyan), the detection (red box + center + angle), and the
pixel coordinates. Open http://armold.local:8091/. Stop:
`sudo systemctl stop oak-stream`.
"""
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import depthai as dai
import numpy as np

PORT = 8091
import json as _json  # noqa: E402

# ROI as fractions of the frame (mat region near the arm; bottom raised to
# exclude power strip / monitor / cables that caused false positives).
ROI_FRAC = (0.20, 0.16, 0.60, 0.656)
MIN_AREA_FRAC = 0.0003
MAX_AREA_FRAC = 0.05
MIN_ELONG = 3.0

_latest = {"jpg": None, "grip": None}
_lock = threading.Lock()


GREEN_LOWER = np.array([35, 70, 50])
GREEN_UPPER = np.array([90, 255, 255])
GREEN_MIN_AREA = 60


def _detect_green(frame):
    """Find up to two green finger blobs; return fingers + grasp midpoint.

    Returns None if no blob, else a dict with:
      fingers: list of (x, y) finger centroids (1 when closed, 2 when open)
      center:  (x, y) grasp point (midpoint of the two fingers, or the
               single blob centroid when closed)
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < GREEN_MIN_AREA:
            continue
        m = cv2.moments(c)
        if m["m00"] == 0:
            continue
        blobs.append((area, m["m10"] / m["m00"], m["m01"] / m["m00"]))
    if not blobs:
        return None
    blobs.sort(key=lambda b: b[0], reverse=True)
    fingers = [(x, y) for _, x, y in blobs[:2]]
    cx = sum(f[0] for f in fingers) / len(fingers)
    cy = sum(f[1] for f in fingers) / len(fingers)
    return {"fingers": fingers, "center": (cx, cy)}


def _detect_pen(frame):
    h, w = frame.shape[:2]
    x0 = int(ROI_FRAC[0] * w)
    y0 = int(ROI_FRAC[1] * h)
    x1 = int(ROI_FRAC[2] * w)
    y1 = int(ROI_FRAC[3] * h)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sub = cv2.GaussianBlur(gray[y0:y1, x0:x1], (5, 5), 0)
    bg = cv2.GaussianBlur(sub, (0, 0), sigmaX=max(9.0, 0.03 * w))
    diff = cv2.absdiff(sub, bg)
    diff = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX).astype("uint8")
    _, mask = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = w * h
    best = None
    best_score = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_AREA_FRAC * frame_area or area > MAX_AREA_FRAC * frame_area:
            continue
        rect = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), angle = rect
        long_side, short_side = max(rw, rh), max(min(rw, rh), 1.0)
        elong = long_side / short_side
        if elong < MIN_ELONG:
            continue
        score = elong * np.sqrt(area)
        if score > best_score:
            best_score = score
            box = cv2.boxPoints(rect).astype(np.int32) + np.array([x0, y0])
            best = (box, (cx + x0, cy + y0), long_side, short_side, angle)
    return (x0, y0, x1, y1), best


def _camera_loop():
    with dai.Pipeline() as pipeline:
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        out = cam.requestOutput((640, 360), dai.ImgFrame.Type.BGR888i, fps=15)
        q = out.createOutputQueue(maxSize=4, blocking=False)
        pipeline.start()
        while pipeline.isRunning():
            frame = q.get().getCvFrame()
            green = _detect_green(frame)
            grip_result = None
            if green is not None:
                gcx, gcy = green["center"]
                grip_result = {
                    "center": [gcx, gcy],
                    "n": len(green["fingers"]),
                    "fingers": [[fx, fy] for fx, fy in green["fingers"]],
                }
                for fx, fy in green["fingers"]:
                    cv2.circle(frame, (int(fx), int(fy)), 5, (255, 0, 255), 2)
                gx, gy = green["center"]
                cv2.drawMarker(
                    frame, (int(gx), int(gy)), (0, 255, 255),
                    cv2.MARKER_CROSS, 16, 2,
                )
                cv2.putText(
                    frame,
                    f"grip ({int(gx)},{int(gy)}) n={len(green['fingers'])}",
                    (int(gx) + 8, int(gy) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 255, 255),
                    1,
                )
            (rx0, ry0, rx1, ry1), best = _detect_pen(frame)
            cv2.rectangle(frame, (rx0, ry0), (rx1, ry1), (255, 200, 0), 1)
            if best is not None:
                box, (gcx, gcy), long_side, short_side, angle = best
                cv2.drawContours(frame, [box], 0, (0, 0, 255), 2)
                cv2.circle(frame, (int(gcx), int(gcy)), 4, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    f"pen ({int(gcx)},{int(gcy)}) {angle:.0f}deg",
                    (rx0, max(12, ry0 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 0, 255),
                    1,
                )
            else:
                cv2.putText(
                    frame,
                    "no pen",
                    (rx0, max(12, ry0 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 180, 255),
                    1,
                )
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with _lock:
                if ok:
                    _latest["jpg"] = buf.tobytes()
                _latest["grip"] = grip_result


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='margin:0;background:#111;text-align:center'>"
                b"<img src='/stream' style='max-width:100%;height:auto'></body></html>"
            )
            return
        if self.path == "/grip":
            with _lock:
                grip = _latest["grip"]
            body = _json.dumps(grip if grip is not None else {}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            try:
                while True:
                    with _lock:
                        jpg = _latest["jpg"]
                    if jpg is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpg)).encode()
                        + b"\r\n\r\n"
                        + jpg
                        + b"\r\n"
                    )
                    time.sleep(1 / 15)
            except (BrokenPipeError, ConnectionResetError):
                return
        self.send_error(404)

    def log_message(self, *args):
        pass


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    threading.Thread(target=_camera_loop, daemon=True).start()
    print(f"OAK detect stream on :{PORT}")
    _ThreadingHTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()


if __name__ == "__main__":
    main()
