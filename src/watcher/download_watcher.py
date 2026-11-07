"""
Downloads folder watcher.

Polls the Downloads folder (no extra dependencies, works the same on Windows,
macOS and Linux). Every file that appears AFTER the watcher started - from any
app: browsers, WhatsApp, Teams, mail, etc. - is renamed once it has finished
downloading (size stable, not locked), using the same engine as the desktop app.
"""

import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Set

logger = logging.getLogger("SmartFileOrganizer")

# Files still being written by a browser or downloader
TEMP_SUFFIXES = (
    ".crdownload", ".part", ".partial", ".tmp", ".temp", ".download", ".opdownload",
    ".!ut", ".!qb", ".aria2", ".filepart", ".crswap", ".dtapart",
)
IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", ".localized"}

# Already organized (by BeeOrganizer, the Chrome extension, or by hand): "26-11 Name.pdf"
ALREADY_ORGANIZED = re.compile(r"^\d{2}-\d{2}[ _]")


def is_candidate(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if lower in IGNORED_NAMES or name.startswith((".", "~$", "~lock")):
        return False
    if lower.endswith(TEMP_SUFFIXES):
        return False
    if ALREADY_ORGANIZED.match(name):
        return False
    return True


class DownloadWatcher(threading.Thread):
    """
    on_event(dict) is called for every processed file with the processor's result
    (status RENAMED / UNCHANGED / SKIPPED / ERROR, original_name, new_name, session_id...).
    process(path) does the real work and returns that dict.
    """

    def __init__(
        self,
        folder: Path,
        process: Callable[[Path], Dict],
        on_event: Optional[Callable[[Dict], None]] = None,
        interval: float = 2.0,
        settle_seconds: float = 3.0,
    ):
        super().__init__(daemon=True, name="DownloadWatcher")
        self.folder = Path(folder)
        self.process = process
        self.on_event = on_event or (lambda e: None)
        self.interval = interval
        self.settle_seconds = settle_seconds

        self._stop = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._known: Set[str] = set()          # names already seen (never process again)
        self._pending: Dict[str, tuple] = {}   # name -> (first_seen, last_size, last_change)

    # ---- control ---------------------------------------------------------
    def stop(self) -> None:
        self._stop.set()

    def pause(self, paused: bool = True) -> None:
        (self._paused.set if paused else self._paused.clear)()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def ignore(self, name: str) -> None:
        """Never process this file name (e.g. a file restored by Undo)."""
        with self._lock:
            self._known.add(name)
            self._pending.pop(name, None)

    # ---- loop --------------------------------------------------------------
    def _list(self) -> Dict[str, Path]:
        out = {}
        try:
            for entry in self.folder.iterdir():
                try:
                    if entry.is_file():
                        out[entry.name] = entry
                except OSError:
                    continue
        except OSError as e:
            logger.warning("Cannot read %s: %s", self.folder, e)
        return out

    def snapshot_existing(self) -> None:
        """Files already in Downloads when we start are left alone."""
        with self._lock:
            self._known = set(self._list())

    def poll_once(self, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        files = self._list()
        ready = []
        with self._lock:
            # forget names that disappeared so a later re-download is processed
            self._known &= set(files)
            for name in list(self._pending):
                if name not in files:
                    del self._pending[name]

            for name, path in files.items():
                if name in self._known:
                    continue
                if not is_candidate(path):
                    self._known.add(name)
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                first, last_size, last_change = self._pending.get(name, (now, -1, now))
                if size != last_size:
                    last_change = now
                self._pending[name] = (first, size, last_change)
                if now - last_change >= self.settle_seconds and size > 0:
                    ready.append(name)

            for name in ready:
                self._pending.pop(name, None)
                self._known.add(name)

        for name in ready:
            if self._paused.is_set() or self._stop.is_set():
                with self._lock:
                    self._known.discard(name)  # retry after resume
                continue
            self._handle(files[name])

    def _handle(self, path: Path) -> None:
        try:
            result = self.process(path)
        except Exception as e:  # never let one file kill the watcher
            logger.exception("Watcher failed on %s", path)
            result = {"status": "ERROR", "original_name": path.name, "new_name": path.name, "message": str(e)}
        new_path = result.get("new_path")
        if new_path:
            p = Path(new_path)
            if p.parent == self.folder:
                with self._lock:
                    self._known.add(p.name)  # don't process our own output
        self.on_event(result)

    def run(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.snapshot_existing()
        logger.info("Watching %s for new downloads", self.folder)
        while not self._stop.is_set():
            if not self._paused.is_set():
                self.poll_once()
            self._stop.wait(self.interval)
