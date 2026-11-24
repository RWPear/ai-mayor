"""Watching Emberfall: a local server for the 3D viewer, and recorders that turn a run into timelapses.

  ./kingdom serve                         # http://localhost:8765 - walk around the latest run in your browser
  ./kingdom record                        # every recorder in content/recorders.yaml, every day -> videos
  ./kingdom record --recorders overview --every 60      # one recorder, a picture every game hour

The viewer (viewer/) is a static page; the server just hands it the run's scene files (days/scenes.json lists
them) and the recorder list. The recorder opens that same page in headless Chrome (Playwright), asks it to show
day N at hh:mm from recorder X (window.kingdom.show), takes a screenshot, and ffmpeg stitches the frames.

On brainbox:  pip install playwright && python -m playwright install chromium   (and apt install ffmpeg)
"""
import http.server
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import yaml

from .config import ROOT

VIEWER = ROOT / "viewer"


def recorders():
    p = ROOT / "content" / "recorders.yaml"
    return (yaml.safe_load(p.read_text()) or {}).get("recorders", []) if p.exists() else []


def scenes_index(days):
    """days/scenes.json: the scene files in a run, oldest first."""
    days = Path(days)
    out = []
    for f in sorted(days.glob("day*.scene.json")):
        try:
            out.append({"day": int(f.name[3:6]), "file": f.name})
        except ValueError:
            continue
    (days / "scenes.json").write_text(json.dumps(out))
    return out


def viewer_version():
    """Changes whenever the viewer's code does. The page is served under /v<version>/, so a browser can never mix
    in old copies of scripts it cached on an earlier visit (Chrome reuses cached modules even on a reload)."""
    newest = max((f.stat().st_mtime_ns for f in VIEWER.rglob("*") if f.suffix in (".js", ".html", ".css")), default=0)
    return format(newest // 1_000_000 % (1 << 40), "x")


class Versioned(http.server.SimpleHTTPRequestHandler):
    """Serves index.html with <base href="/v<version>/">, and strips that prefix from every request."""
    version = None

    def _unversion(self):
        m = re.match(r"^/v[0-9a-f]+(/.*)$", self.path)
        if m:
            self.path = m.group(1)

    def _index(self):
        ver = self.version or viewer_version()
        html = (VIEWER / "index.html").read_text()
        html = html.replace("<head>", f'<head>\n<base href="/v{ver}/">', 1)
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._unversion()
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            return self._index()
        return super().do_GET()

    def do_HEAD(self):
        self._unversion()
        return super().do_HEAD()


class _Handler(Versioned):
    days = None

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path.startswith("/days/"):
            if path.endswith("/scenes.json"):
                scenes_index(self.days)
            return str(Path(self.days) / path[len("/days/"):])
        if path == "/recorders.json":
            f = Path(self.days) / ".recorders.json"
            f.write_text(json.dumps(recorders()))
            return str(f)
        return str(VIEWER / (path.lstrip("/") or "index.html"))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def serve(days, port=8765, block=True):
    days = Path(days).resolve()
    if not days.exists():
        raise SystemExit(f"No run at {days} - run a frontier scenario with --reports first.")
    scenes_index(days)
    handler = type("H", (_Handler,), {"days": str(days)})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1" if not block else "0.0.0.0", port), handler)
    if not block:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    print(f"Emberfall is at http://localhost:{port}  (days from {days}; Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def _times(rec, every, start="06:00", end="20:00"):
    if every:
        h0, h1 = (int(start[:2]) * 60 + int(start[3:])), (int(end[:2]) * 60 + int(end[3:]))
        return list(range(h0, h1 + 1, every))
    return [int(t[:2]) * 60 + int(t[3:5]) for t in rec.get("times", ["12:00"])]


def record(days, names=None, every=None, size="1280x720", quality="high", fps=10, out=None, only_day=None,
           gpu=True, three=None, port=8799, first=None, last=None):
    """Renders each recorder's frames for each day, then one video per recorder (and a stills folder)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("The recorders need Playwright: pip install playwright && python -m playwright install chromium")
    days = Path(days).resolve()
    out = Path(out) if out else days.parent / "recordings"
    out.mkdir(parents=True, exist_ok=True)
    index = scenes_index(days)
    if only_day is not None:
        index = [d for d in index if d["day"] == only_day]
    index = [d for d in index if (first is None or d["day"] >= first) and (last is None or d["day"] <= last)]
    if not index:
        raise SystemExit(f"No scene files in {days}.")
    recs = [r for r in recorders() if not names or r["name"] in names]
    w, h = (int(x) for x in size.lower().split("x"))
    srv = serve(days, port=port, block=False)
    args = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization"] + (
        ["--use-angle=default"] if gpu else ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    made = {}
    t0 = time.time()
    with sync_playwright() as p:
        launch = {"args": args}
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        if chrome:
            launch["executable_path"] = chrome
        browser = p.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": w, "height": h})
        if three:                                   # offline: serve three.js from a local copy of the npm package
            three = Path(three)

            def route(r):
                url = r.request.url
                if "three@" in url:
                    r.fulfill(path=str(three / url.split("/npm/")[1].split("/", 1)[1]), content_type="application/javascript")
                else:
                    r.continue_()
            page.route("**/*", route)
        page.goto(f"http://127.0.0.1:{port}/?record=1&quality={quality}")
        page.wait_for_function("window.kingdom && window.kingdom.ready === true", timeout=120000)
        for rec in recs:
            folder = out / rec["name"]
            folder.mkdir(exist_ok=True)
            for d in index:                         # frames are named by day and time: re-recording a day replaces it
                for old in folder.glob(f"day{d['day']:03d}_*.png"):
                    old.unlink()
                for minute in _times(rec, every):
                    page.evaluate("(a) => window.kingdom.show(a)", {"day": d["day"], "minute": minute,
                                                                    "recorder": rec["name"], "frames": 4})
                    page.screenshot(path=str(folder / f"day{d['day']:03d}_{minute // 60:02d}{minute % 60:02d}.png"))
            made[rec["name"]] = len(list(folder.glob("day*.png")))
            print(f"  {rec['name']}: {made[rec['name']]} frames")
        browser.close()
    srv.shutdown()
    videos = []
    if shutil.which("ffmpeg"):
        for name in made:
            folder = out / name
            frames = sorted(folder.glob("day*.png"))
            if len(frames) < 2:
                continue
            listing = folder / "frames.txt"
            listing.write_text("".join(f"file '{f.name}'\nduration {1 / fps:.4f}\n" for f in frames)
                               + f"file '{frames[-1].name}'\n")
            video = out / f"{name}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                            "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            str(video)], check=True)
            videos.append(video)
    else:
        print("  (no ffmpeg - frames only)")
    print(f"Recorded {sum(made.values())} frames in {time.time() - t0:.0f}s -> {out}")
    for v in videos:
        print(f"  {v}")
    return videos
