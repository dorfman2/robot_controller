"""Grab one JPEG frame from the local MJPEG stream and save it."""
import urllib.request

data = b""
with urllib.request.urlopen("http://localhost:8091/stream", timeout=4) as r:
    while len(data) < 400000:
        chunk = r.read(8192)
        if not chunk:
            break
        data += chunk
start = data.find(b"\xff\xd8")
end = data.find(b"\xff\xd9", start)
if start >= 0 and end > start:
    with open("/home/pi/stream_frame.jpg", "wb") as f:
        f.write(data[start : end + 2])
    print("saved frame bytes:", end + 2 - start)
else:
    print("no JPEG found in stream")
