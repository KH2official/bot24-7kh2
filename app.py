#!/usr/bin/env python3
"""
Single-page bot host (Flask) with:
- Upload .zip / .py / .js
- Unzip automatically
- Multiple tokens
- Start / Stop / Restart / Fix Bugs controls (AJAX)
- Live console via Server-Sent Events (SSE) — single-page UI, no navigation
Run:
    pip install -r requirements.txt
    python app.py
"""
import os
import sys
import shutil
import threading
import subprocess
import time
from collections import deque
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
import utils

APP_ROOT = Path(__file__).parent.resolve()
USERBOT_DIR = APP_ROOT / "userbot"
LOG_FILE = APP_ROOT / "console.log"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB upload limit (adjust)

# Runtime state
state = {
    "process": None,
    "process_lock": threading.Lock(),
    "tokens": [],
    "mainfile": None,
    "last_error": "",
    "log_lines": deque([], maxlen=5000),
    "log_event": threading.Event(),
    "log_thread": None,
}


def append_log(line: str):
    text = line.rstrip("\n")
    state["log_lines"].append(text)
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(text + "\n")
    except Exception:
        pass
    state["log_event"].set()


def clear_logs():
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
    except Exception:
        pass
    state["log_lines"].clear()
    state["log_event"].set()


def spawn_log_reader(proc: subprocess.Popen):
    """Reads process stdout and pushes lines into append_log. Runs in background thread."""
    def reader():
        try:
            if proc.stdout is None:
                return
            for raw in iter(proc.stdout.readline, b""):
                if not raw:
                    break
                try:
                    line = raw.decode("utf-8", errors="replace")
                except Exception:
                    line = str(raw)
                append_log(line)
        except Exception as e:
            append_log(f"[host] log reader error: {e}")
        finally:
            try:
                rc = proc.poll()
                if rc is None:
                    proc.wait(timeout=1)
                    rc = proc.returncode
            except Exception:
                rc = getattr(proc, "returncode", None)
            append_log(f"[host] process exited with code {rc}")
            with state["process_lock"]:
                state["process"] = None
            state["log_event"].set()
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    state["log_thread"] = t


def start_bot():
    with state["process_lock"]:
        if state["process"] is not None:
            return {"ok": False, "error": "Bot already running."}
        if not USERBOT_DIR.exists():
            return {"ok": False, "error": "No uploaded code. Upload code first."}
        mainfile = state["mainfile"]
        if not mainfile:
            mf = utils.detect_main_file(USERBOT_DIR)
            if mf:
                state["mainfile"] = mf
                mainfile = mf
            else:
                return {"ok": False, "error": "Main bot file not found (.py or .js)."}
        env = os.environ.copy()
        for i, tkn in enumerate(state["tokens"]):
            env_key = f"BOT_TOKEN{i+1}"
            env[env_key] = tkn
        try:
            append_log("[host] checking & installing dependencies (if any)...")
            utils.fix_dependencies(USERBOT_DIR)
        except Exception as e:
            append_log(f"[host] dependency install warning: {e}")
        try:
            clear_logs()
            append_log(f"[host] starting {mainfile} ...")
            if str(mainfile).endswith(".js"):
                cmd = ["node", str(mainfile)]
            elif str(mainfile).endswith(".py"):
                cmd = [sys.executable, str(mainfile)]
            else:
                return {"ok": False, "error": f"Unsupported main file type: {mainfile}"}
            proc = subprocess.Popen(
                cmd,
                cwd=str(USERBOT_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            state["process"] = proc
            spawn_log_reader(proc)
            return {"ok": True}
        except FileNotFoundError as e:
            return {"ok": False, "error": f"Executable not found: {e}. Make sure node/python is installed."}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def stop_bot():
    with state["process_lock"]:
        p = state["process"]
        if not p:
            return {"ok": False, "error": "No running bot."}
        try:
            append_log("[host] stopping process ...")
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
                p.wait(timeout=2)
            append_log("[host] process stopped.")
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            state["process"] = None
    return {"ok": True}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    try:
        token = request.form.get("token", "").strip()
        file = request.files.get("file")
        if not token:
            return jsonify({"ok": False, "error": "Token is required."}), 400
        if not file:
            return jsonify({"ok": False, "error": "File is required."}), 400
        filename = secure_filename(file.filename)
        if not utils.allowed_file(filename):
            return jsonify({"ok": False, "error": "Invalid file type. Allowed: zip, py, js."}), 400
        if USERBOT_DIR.exists():
            shutil.rmtree(USERBOT_DIR, ignore_errors=True)
        USERBOT_DIR.mkdir(parents=True, exist_ok=True)
        saved_path = USERBOT_DIR / filename
        file.save(str(saved_path))
        try:
            utils.unzip_and_fix(saved_path, USERBOT_DIR)
        except Exception as e:
            state["last_error"] = str(e)
            append_log(f"[host] upload error: {e}")
            return jsonify({"ok": False, "error": f"Upload/extract failed: {e}"}), 400
        mf = utils.detect_main_file(USERBOT_DIR)
        state["mainfile"] = mf
        state["tokens"] = [token]
        res = start_bot()
        if not res.get("ok"):
            state["last_error"] = res.get("error", "unknown")
            return jsonify({"ok": False, "error": res.get("error")}), 400
        return jsonify({"ok": True, "mainfile": state["mainfile"]})
    except Exception as e:
        state["last_error"] = str(e)
        append_log(f"[host] unexpected upload error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/add_token", methods=["POST"])
def api_add_token():
    try:
        data = request.get_json(force=True)
        token = (data.get("token") or "").strip()
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    if not token:
        return jsonify({"ok": False, "error": "Token required"}), 400
    state["tokens"].append(token)
    append_log(f"[host] added token (count={len(state['tokens'])})")
    return jsonify({"ok": True, "tokens": state["tokens"]})


@app.route("/api/start", methods=["POST"])
def api_start():
    res = start_bot()
    if not res.get("ok"):
        state["last_error"] = res.get("error", "")
        append_log(f"[host] start failed: {res.get('error')}")
        return jsonify(res), 400
    return jsonify(res)


@app.route("/api/stop", methods=["POST"])
def api_stop():
    res = stop_bot()
    if not res.get("ok"):
        append_log(f"[host] stop failed: {res.get('error')}")
        return jsonify(res), 400
    return jsonify(res)


@app.route("/api/restart", methods=["POST"])
def api_restart():
    stop_bot()
    time.sleep(0.5)
    res = start_bot()
    if not res.get("ok"):
        state["last_error"] = res.get("error", "")
        append_log(f"[host] restart failed: {res.get('error')}")
        return jsonify(res), 400
    return jsonify(res)


@app.route("/api/fixbugs", methods=["POST"])
def api_fixbugs():
    try:
        append_log("[host] trying to fix bugs: (reinstall deps if present)")
        utils.fix_dependencies(USERBOT_DIR)
        append_log("[host] fixbugs: dependency step finished.")
        return jsonify({"ok": True})
    except Exception as e:
        append_log(f"[host] fixbugs failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    running = False
    with state["process_lock"]:
        p = state["process"]
        running = bool(p and p.poll() is None)
    return jsonify({
        "running": running,
        "tokens": state["tokens"],
        "mainfile": state["mainfile"],
        "last_error": state["last_error"],
    })


@app.route("/api/logs", methods=["GET"])
def api_logs():
    return jsonify({"lines": list(state["log_lines"])})


@app.route("/stream")
def stream():
    def event_stream():
        for line in list(state["log_lines"]):
            yield f"data: {line.replace('\\n', ' ')}\n\n"
        state["log_event"].clear()
        last_sent = len(state["log_lines"])
        while True:
            state["log_event"].wait(timeout=15)
            # send new lines only
            lines = list(state["log_lines"])
            if len(lines) > last_sent:
                for line in lines[last_sent:]:
                    yield f"data: {line.replace('\\n', ' ')}\n\n"
                last_sent = len(lines)
            state["log_event"].clear()
    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    (APP_ROOT / "static").mkdir(exist_ok=True)
    USERBOT_DIR.mkdir(exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    print("Starting host on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, threaded=True)