from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, jsonify, render_template, request, send_file

IMAGE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

CONFIG_PATH = Path(__file__).with_name("config.json")
MIN_DELAY_MS = 250
CONFIG_POLL_SECONDS = 1.0


class SlideshowState:
    def __init__(self) -> None:
        self.images: list[dict[str, object]] = []
        self.current_index = 0
        self.delay_ms = 3000
        self.is_playing = False
        self.delay_override = False
        self.last_error: str | None = None
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def apply_config(self, images: list[dict[str, object]], delay_ms: int) -> None:
        with self.condition:
            was_playing = self.is_playing
            self.images = images
            self.current_index = 0
            if not self.delay_override:
                self.delay_ms = delay_ms
            self.is_playing = was_playing and bool(images)
            self.last_error = None
            self.condition.notify_all()

    def set_delay(self, delay_ms: int) -> None:
        with self.condition:
            self.delay_ms = delay_ms
            self.delay_override = True
            self.condition.notify_all()

    def start(self) -> None:
        with self.condition:
            if not self.images:
                raise ValueError("No images loaded")
            self.is_playing = True
            self.condition.notify_all()

    def stop(self) -> None:
        with self.condition:
            self.is_playing = False
            self.condition.notify_all()

    def reset(self) -> None:
        with self.condition:
            self.current_index = 0
            self.condition.notify_all()

    def set_error(self, message: str) -> None:
        with self.condition:
            self.images = []
            self.current_index = 0
            self.is_playing = False
            self.last_error = message
            self.condition.notify_all()

    def advance(self) -> None:
        if not self.images:
            self.is_playing = False
            return
        self.current_index = (self.current_index + 1) % len(self.images)


def load_config() -> tuple[Path, int]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    folder_path = str(data.get("folder_path") or "").strip()
    if not folder_path:
        raise ValueError("folder_path is required in config.json")

    delay_seconds = data.get("delay_seconds", 3)
    try:
        delay_seconds_float = float(delay_seconds)
    except (TypeError, ValueError):
        raise ValueError("delay_seconds must be a number")

    if delay_seconds_float <= 0:
        raise ValueError("delay_seconds must be greater than 0")

    delay_ms = int(round(delay_seconds_float * 1000))
    delay_ms = max(delay_ms, MIN_DELAY_MS)

    return Path(folder_path).expanduser().resolve(), delay_ms


def load_images(folder_path: Path) -> list[dict[str, object]]:
    if not folder_path.is_dir():
        raise ValueError("folder_path must be a directory")

    files = [
        file
        for file in sorted(folder_path.iterdir())
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not files:
        raise ValueError("No image files found in that folder")

    images: list[dict[str, object]] = []
    for index, file in enumerate(files):
        name = file.name
        url = f"/images/{index}/{quote(name)}"
        images.append({"name": name, "path": file, "url": url})

    return images


def apply_config(state: SlideshowState) -> None:
    try:
        folder_path, delay_ms = load_config()
        images = load_images(folder_path)
    except Exception as exc:
        state.set_error(str(exc))
        return

    state.apply_config(images, delay_ms)


def slideshow_worker(state: SlideshowState) -> None:
    while True:
        with state.condition:
            while not state.is_playing:
                state.condition.wait()
            delay_seconds = max(state.delay_ms, MIN_DELAY_MS) / 1000.0
        time.sleep(delay_seconds)
        with state.condition:
            if state.is_playing:
                state.advance()


def config_watcher(state: SlideshowState) -> None:
    last_mtime: float | None = None

    while True:
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except FileNotFoundError:
            if last_mtime is not None:
                state.set_error(f"Config file not found at {CONFIG_PATH}")
                last_mtime = None
            time.sleep(CONFIG_POLL_SECONDS)
            continue

        if last_mtime is None or mtime != last_mtime:
            last_mtime = mtime
            apply_config(state)

        time.sleep(CONFIG_POLL_SECONDS)


state = SlideshowState()
apply_config(state)

slideshow_thread = threading.Thread(target=slideshow_worker, args=(state,), daemon=True)
slideshow_thread.start()

config_thread = threading.Thread(target=config_watcher, args=(state,), daemon=True)
config_thread.start()

app = Flask(__name__, static_folder="static", template_folder="templates")


def build_status(
    images: list[dict[str, object]],
    current_index: int,
    is_playing: bool,
    last_error: str | None,
) -> str:
    if not images:
        if last_error:
            return f"Config error: {last_error}"
        return "No images loaded."
    index = current_index % len(images)
    name = images[index]["name"]
    if is_playing:
        return f"Playing: {index + 1} of {len(images)} ({name})"
    return f"Stopped at {index + 1} of {len(images)} ({name})"


def serialize_state() -> dict[str, object]:
    with state.lock:
        images_snapshot = list(state.images)
        total = len(images_snapshot)
        current_index = state.current_index
        delay_ms = state.delay_ms
        is_playing = state.is_playing
        last_error = state.last_error
        current_image = None
        if total:
            index = current_index % total
            image = images_snapshot[index]
            current_image = {
                "index": index,
                "total": total,
                "name": image["name"],
                "url": image["url"],
            }
        return {
            "images_count": total,
            "current_index": current_index,
            "delay_ms": delay_ms,
            "is_playing": is_playing,
            "current_image": current_image,
            "status": build_status(images_snapshot, current_index, is_playing, last_error),
            "error": last_error,
        }


@app.get("/")
def viewer() -> str:
    return render_template("viewer.html")


@app.get("/viewer")
def viewer_alias() -> str:
    return render_template("viewer.html")


@app.get("/api/state")
def api_state():
    return jsonify(serialize_state())


@app.post("/api/set_delay")
def api_set_delay():
    payload = request.get_json(silent=True) or {}
    delay_ms = payload.get("delay_ms")

    try:
        delay_ms_int = int(delay_ms)
    except (TypeError, ValueError):
        return jsonify({"error": "delay_ms must be an integer"}), 400

    if delay_ms_int < MIN_DELAY_MS:
        return jsonify({"error": f"delay_ms must be at least {MIN_DELAY_MS}"}), 400

    state.set_delay(delay_ms_int)
    return jsonify({"ok": True})


@app.post("/api/start")
def api_start():
    try:
        state.start()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.post("/api/stop")
def api_stop():
    state.stop()
    return jsonify({"ok": True})


@app.post("/api/reset")
def api_reset():
    state.reset()
    return jsonify({"ok": True})


@app.get("/images/<int:index>/<path:filename>")
def images(index: int, filename: str):
    with state.lock:
        if index < 0 or index >= len(state.images):
            abort(404)
        image = state.images[index]
        if filename != image["name"]:
            abort(404)
        path = image["path"]

    if not isinstance(path, Path) or not path.exists():
        abort(404)

    return send_file(path, conditional=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)
