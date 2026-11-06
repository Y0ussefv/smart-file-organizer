"""
Native Messaging host for the Smart File Organizer browser extension.

Chrome/Edge/Brave launch this process and talk to it over stdin/stdout using
length-prefixed JSON (4-byte little-endian length + UTF-8 JSON).

Supported requests:
  {"action": "ping"}
  {"action": "process", "path": "...", "url": "...", "folder_mode": "none|site|type",
   "dry_run": false, "add_date_prefix": null}
  {"action": "undo", "session_id": "..."}
  {"action": "reveal", "path": "..."}
  {"action": "open", "path": "..."}
"""

import json
import os
import struct
import subprocess
import sys
import traceback
from pathlib import Path

# Make "src.*" importable when launched directly by the browser.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HOST_NAME = "com.rnj.smartfileorganizer"
VERSION = "1.0.0"


def _read_message(stream):
    raw_len = stream.read(4)
    if len(raw_len) < 4:
        return None
    (length,) = struct.unpack("<I", raw_len)
    data = stream.read(length)
    return json.loads(data.decode("utf-8"))


def _write_message(stream, message) -> None:
    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(data)))
    stream.write(data)
    stream.flush()


def _reveal(path: str, select: bool = True) -> dict:
    p = Path(path)
    if not p.exists():
        return {"status": "ERROR", "message": "File no longer exists."}
    if sys.platform.startswith("win"):
        if select:
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)] if select else ["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if select else p)])
    return {"status": "OK"}


def handle(message: dict) -> dict:
    action = (message or {}).get("action")

    if action == "ping":
        return {"status": "OK", "host": HOST_NAME, "version": VERSION}

    if action in ("process", "undo"):
        from src.integrations.download_processor import DownloadProcessor
        processor = DownloadProcessor()
        if action == "process":
            return processor.process(
                message.get("path", ""),
                source_url=message.get("url"),
                folder_mode=message.get("folder_mode", "none"),
                dry_run=bool(message.get("dry_run", False)),
                add_date_prefix=message.get("add_date_prefix"),
            )
        return processor.undo(message.get("session_id", ""))

    if action == "reveal":
        return _reveal(message.get("path", ""), select=True)
    if action == "open":
        return _reveal(message.get("path", ""), select=False)

    return {"status": "ERROR", "message": f"Unknown action: {action!r}"}


def main() -> None:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    # Anything printed by libraries must NOT corrupt the protocol stream.
    sys.stdout = sys.stderr

    try:
        from src.utils.logging_config import setup_logging
        setup_logging(log_file_name="browser_bridge.log")
    except Exception:
        pass

    while True:
        try:
            message = _read_message(stdin)
        except Exception as e:
            _write_message(stdout, {"status": "ERROR", "message": f"Bad message: {e}"})
            return
        if message is None:
            return  # browser closed the pipe
        try:
            reply = handle(message)
        except Exception as e:
            traceback.print_exc()
            reply = {"status": "ERROR", "message": str(e)}
        if isinstance(message, dict) and "request_id" in message:
            reply["request_id"] = message["request_id"]
        _write_message(stdout, reply)


if __name__ == "__main__":
    main()
