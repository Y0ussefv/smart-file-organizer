"""
Downloads folder watcher.

Polls the Downloads folder (no extra dependencies, works the same on Windows,
macOS and Linux). Every file that appears AFTER the watcher started - from any
app: browsers, WhatsApp, Teams, mail, etc. - is renamed once it has finished
downloading (size stable, not locked), using the same engine as the desktop app.
"""

import logging
import os
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


def file_in_use(path: Path) -> bool:
    """
    True while another program still has the file open (Windows only).

    After Chrome/Edge finish a download they ask Windows Defender to scan it;
    renaming the file during that scan makes the browser show "Virus scan failed".
    Opening the file with no sharing fails while anyone else holds it open.
    """
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    GENERIC_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL = 0x80000000, 3, 0x80
    handle = kernel32.CreateFileW(str(path), GENERIC_READ, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if handle == wintypes.HANDLE(-1).value:
        return ctypes.get_last_error() in (32, 33)  # sharing / lock violation
    kernel32.CloseHandle(handle)
    return False


BUNDLE_DIR_SUFFIXES = (".app", ".bundle", ".framework", ".download", ".pkg", ".photoslibrary")


def is_folder_candidate(path: Path) -> bool:
    name = path.name
    if name.startswith((".", "~")) or name.lower() in IGNORED_NAMES or name.lower() == "__macosx":
        return False
    if name.lower().endswith(BUNDLE_DIR_SUFFIXES):
        return False
    return not ALREADY_ORGANIZED.match(name)


def folder_signature(path: Path, limit: int = 20000) -> tuple:
    """(file count, total size) - stops changing when a copy / unzip has finished."""
    count = total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
            count += 1
            if count >= limit:
                return (count, total)
    return (count, total)


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
    on_event(dict) is called for every processed file / folder with the result
    (status RENAMED / ORGANIZED / UNCHANGED / SKIPPED / ERROR, original_name, new_name, session_id...).
    process(path) handles a new file; process_dir(path) a new folder (optional).
    Results may list "folders" they created so they are not treated as new downloads.
    """

    def __init__(
        self,
        folder: Path,
        process: Callable[[Path], Dict],
        on_event: Optional[Callable[[Dict], None]] = None,
        interval: float = 2.0,
        settle_seconds: float = 6.0,
        process_dir: Optional[Callable[[Path], Dict]] = None,
    ):
        super().__init__(daemon=True, name="DownloadWatcher")
        self.folder = Path(folder)
        self.process = process
        self.on_event = on_event or (lambda e: None)
        self.interval = interval
        self.settle_seconds = settle_seconds
        self.dir_settle_seconds = settle_seconds * 2
        self.process_dir = process_dir

        self._stop = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._known: Set[str] = set()          # names already seen (never process again)
        self._pending: Dict[str, tuple] = {}   # name -> (first_seen, last_signature, last_change)

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
                    if entry.is_file() or entry.is_dir():
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
                is_dir = path.is_dir()
                ok = (is_folder_candidate(path) and self.process_dir is not None) if is_dir else is_candidate(path)
                if not ok:
                    self._known.add(name)
                    continue
                try:
                    sig = folder_signature(path) if is_dir else path.stat().st_size
                except OSError:
                    continue
                first, last_sig, last_change = self._pending.get(name, (now, None, now))
                if sig != last_sig:
                    last_change = now
                self._pending[name] = (first, sig, last_change)
                settle = self.dir_settle_seconds if is_dir else self.settle_seconds
                has_content = sig[0] > 0 if is_dir else sig > 0
                if now - last_change >= settle and has_content and last_sig is not None:
                    if not is_dir and file_in_use(path):
                        # still open (browser virus scan, copy in progress...): wait longer
                        self._pending[name] = (first, sig, now)
                        continue
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
            result = (self.process_dir(path) if path.is_dir() else self.process(path)) or {}
        except Exception as e:  # never let one file kill the watcher
            logger.exception("Watcher failed on %s", path)
            result = {"status": "ERROR", "original_name": path.name, "new_name": path.name, "message": str(e)}
        produced = [result.get("new_path")] + list(result.get("folders") or [])
        with self._lock:
            for item in produced:
                if item and Path(item).parent == self.folder:
                    self._known.add(Path(item).name)  # don't process our own output
        self.on_event(result)

    def run(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.snapshot_existing()
        logger.info("Watching %s for new downloads", self.folder)
        while not self._stop.is_set():
            if not self._paused.is_set():
                self.poll_once()
            self._stop.wait(self.interval)
