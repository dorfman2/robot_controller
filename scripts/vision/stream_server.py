"""
Shared MJPEG HTTP stream server for Armold vision services.

Provides a reusable threaded HTTP server that serves:
    - ``/`` — Simple HTML page embedding the MJPEG stream.
    - ``/stream`` — MJPEG multipart stream (live camera overlay).
    - Custom JSON endpoints (registered by subclass/caller).

Each camera service (overhead, side) instantiates one of these with its
own port and latest-frame producer.
"""

import json
import logging
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Frame store (thread-safe latest-frame buffer)
# ---------------------------------------------------------------------------


class FrameStore:
    """Thread-safe store for the latest JPEG frame and JSON detection data.

    Used by the camera loop (producer) and the HTTP server (consumer) to
    share the most recent frame and detection results without blocking.

    Attributes:
        _lock: Threading lock for safe concurrent access.
        _jpg: Latest JPEG-encoded frame bytes, or None.
        _json_data: Dict of endpoint-name → JSON-serializable detection data.
    """

    def __init__(self) -> None:
        """Initialize an empty FrameStore."""
        self._lock = threading.Lock()
        self._jpg: bytes | None = None
        self._json_data: dict[str, Any] = {}

    def put_frame(self, jpg_bytes: bytes) -> None:
        """Store a new JPEG frame.

        Args:
            jpg_bytes: JPEG-encoded image bytes.
        """
        with self._lock:
            self._jpg = jpg_bytes

    def get_frame(self) -> bytes | None:
        """Retrieve the latest JPEG frame.

        Returns:
            JPEG bytes or None if no frame has been stored yet.
        """
        with self._lock:
            return self._jpg

    def put_json(self, endpoint: str, data: Any) -> None:
        """Store JSON-serializable detection data for a named endpoint.

        Args:
            endpoint: The endpoint name (e.g. 'target', 'grip', 'gap').
            data: JSON-serializable data (dict, list, or None).
        """
        with self._lock:
            self._json_data[endpoint] = data

    def get_json(self, endpoint: str) -> Any:
        """Retrieve detection data for a named endpoint.

        Args:
            endpoint: The endpoint name.

        Returns:
            The stored data, or an empty dict if not set.
        """
        with self._lock:
            return self._json_data.get(endpoint, {})


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def make_handler_class(
    store: FrameStore,
    fps: float = 15.0,
    json_endpoints: list[str] | None = None,
    index_title: str = "Armold Camera Stream",
) -> type:
    """Create an HTTP request handler class bound to a FrameStore.

    The handler serves:
        GET /          — HTML page with embedded MJPEG stream.
        GET /stream    — MJPEG multipart stream.
        GET /<endpoint> — JSON detection data (for each registered endpoint).

    Args:
        store: The FrameStore providing frames and JSON data.
        fps: Target frame rate for the MJPEG stream.
        json_endpoints: List of JSON endpoint names (e.g. ['target', 'grip']).
        index_title: Title for the HTML index page.

    Returns:
        A BaseHTTPRequestHandler subclass.
    """
    endpoints = json_endpoints or []

    class Handler(BaseHTTPRequestHandler):
        """MJPEG + JSON HTTP handler for a single camera stream."""

        def do_GET(self) -> None:
            """Handle GET requests for stream, JSON endpoints, and index."""
            if self.path in ("/", "/index.html"):
                self._serve_index()
            elif self.path == "/stream":
                self._serve_stream()
            elif self.path.lstrip("/") in endpoints:
                self._serve_json(self.path.lstrip("/"))
            else:
                self.send_error(404)

        def _serve_index(self) -> None:
            """Serve the HTML index page with an embedded stream image."""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            links = "".join(
                f'<a href="/{ep}" style="color:#0af;margin:0 8px">' f"/{ep}</a>"
                for ep in endpoints
            )
            self.wfile.write(
                f"<html><head><title>{index_title}</title></head>"
                f"<body style='margin:0;background:#111;text-align:center;"
                f"font-family:monospace'>"
                f"<h3 style='color:#ccc;margin:8px'>{index_title}</h3>"
                f"<img src='/stream' style='max-width:100%;height:auto'>"
                f"<p style='color:#888'>JSON: {links}</p>"
                f"</body></html>".encode()
            )

        def _serve_stream(self) -> None:
            """Serve the MJPEG multipart stream."""
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame",
            )
            self.end_headers()
            interval = 1.0 / fps
            try:
                while True:
                    jpg = store.get_frame()
                    if jpg is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: "
                        + str(len(jpg)).encode()
                        + b"\r\n\r\n"
                        + jpg
                        + b"\r\n"
                    )
                    time.sleep(interval)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _serve_json(self, endpoint: str) -> None:
            """Serve JSON detection data for a named endpoint."""
            data = store.get_json(endpoint)
            body = json.dumps(data if data is not None else {}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            """Suppress default HTTP access logging."""

    return Handler


# ---------------------------------------------------------------------------
# Threaded server
# ---------------------------------------------------------------------------


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread.

    Attributes:
        daemon_threads: Threads die when the main thread exits.
        allow_reuse_address: Allow rebinding to the port after restart.
    """

    daemon_threads = True
    allow_reuse_address = True


def start_stream_server(
    store: FrameStore,
    port: int,
    fps: float = 15.0,
    json_endpoints: list[str] | None = None,
    title: str = "Armold Camera",
) -> ThreadingHTTPServer:
    """Create and start an MJPEG stream server in a daemon thread.

    Args:
        store: The FrameStore to serve frames/JSON from.
        port: TCP port to listen on.
        fps: Target MJPEG stream frame rate.
        json_endpoints: List of JSON endpoint names.
        title: Title for the HTML index page.

    Returns:
        The running ThreadingHTTPServer instance.
    """
    handler_cls = make_handler_class(
        store, fps=fps, json_endpoints=json_endpoints, index_title=title
    )
    server = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Stream server started on :%d", port)
    return server
