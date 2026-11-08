"""
BeeOrganizer background mode: an icon near the clock (Windows) / in the menu bar (macOS)
that watches the Downloads folder and renames every new download.

    SmartFileOrganizer.exe --watch        (or: python main.py --watch)
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QLockFile, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from src.integrations.download_processor import DownloadProcessor
from src.organizer.smart_organizer import SmartOrganizer
from src.storage.settings import SettingsManager
from src.utils.platform_utils import get_app_data_dir, get_downloads_dir
from src.watcher import autostart
from src.watcher.download_watcher import DownloadWatcher

logger = logging.getLogger("SmartFileOrganizer")

ICON_PATH = Path(__file__).resolve().parents[1] / "app" / "assets" / "icon.png"
RECENT_LIMIT = 10

DEFAULTS = {
    "watcher_date_prefix": True,     # "26-11 Title.pdf"
    "watcher_type_folders": False,   # Documents/, Images/ ...
    "watcher_smart_folders": True,   # project folders like a human (needs OpenAI key)
    "autostart_asked": False,
}


def _setting(settings: SettingsManager, key: str):
    return settings.get(key, DEFAULTS[key])


class _Bridge(QObject):
    """Carries watcher events from the worker thread to the Qt (GUI) thread."""
    event = Signal(dict)
    plan_ready = Signal(object)
    organize_done = Signal(dict)


class TrayController(QObject):
    def __init__(self, app: QApplication, show_window: bool = False):
        super().__init__()
        self.app = app
        self.settings = SettingsManager()
        self.recent: List[Dict] = []
        self.window = None
        self.folder = Path(self.settings.get("watch_folder", "") or get_downloads_dir())

        self.bridge = _Bridge()
        self.bridge.event.connect(self._on_event)
        self.bridge.plan_ready.connect(self._confirm_plan)
        self.bridge.organize_done.connect(self._on_organized)
        self._organizing = False
        self.watcher = DownloadWatcher(self.folder, self._process, self.bridge.event.emit,
                                       process_dir=self._process_dir)

        icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip(f"BeeOrganizer – watching {self.folder}")
        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.watcher.start()
        if show_window:
            self.open_window()
        QTimer.singleShot(1500, self._first_run)

    # ---- processing (worker thread) -------------------------------------
    def _process(self, path: Path) -> Dict:
        settings = SettingsManager()  # re-read: picks up key / option changes
        result = DownloadProcessor(settings=settings).process(
            str(path),
            folder_mode="type" if _setting(settings, "watcher_type_folders") else "none",
            add_date_prefix=bool(_setting(settings, "watcher_date_prefix")),
            date_prefix_format="%y-%m",
            date_prefix_separator=" ",
        )
        result["session_ids"] = [result["session_id"]] if result.get("session_id") else []

        # Like a human: file it into the matching project folder, if there is one.
        if (_setting(settings, "watcher_smart_folders") and not result.get("subfolder")
                and result.get("status") in ("RENAMED", "UNCHANGED")):
            cur = Path(result.get("new_path") or path)
            if cur.exists() and cur.parent == self.folder:
                organizer = SmartOrganizer(self.folder, settings=settings)
                plan = organizer.plan_placement(cur, title=result.get("detected_title") or "",
                                                file_type=result.get("file_type") or "")
                if plan.moves:
                    placed = organizer.apply(plan, label="Placement")
                    if placed.get("session_id"):
                        dst = plan.moves[0].dst
                        result["session_ids"].append(placed["session_id"])
                        result["new_path"] = str(dst)
                        result["placed_in"] = str(dst.parent.relative_to(self.folder))
                        result["status"] = "RENAMED"
        return result

    def _process_dir(self, path: Path) -> Dict:
        settings = SettingsManager()
        if not _setting(settings, "watcher_smart_folders"):
            return {"status": "SKIPPED", "original_name": path.name, "new_name": path.name}
        result = SmartOrganizer(self.folder, settings=settings).organize_folder(path)
        result["session_ids"] = [result["session_id"]] if result.get("session_id") else []
        result["new_name"] = Path(result["folders"][0]).name if result.get("folders") else path.name
        result["new_path"] = result["folders"][0] if result.get("folders") else str(path)
        result["is_folder"] = True
        return result

    # ---- UI ----------------------------------------------------------------
    def _build_menu(self) -> None:
        m = self.menu
        m.clear()
        self.status_action = QAction(self._status_text())
        self.status_action.setEnabled(False)
        m.addAction(self.status_action)
        m.addSeparator()

        self.pause_action = QAction("Pause renaming", checkable=True)
        self.pause_action.setChecked(self.watcher.paused)
        self.pause_action.toggled.connect(self._toggle_pause)
        m.addAction(self.pause_action)

        self.recent_menu = m.addMenu("Recent renames")
        self._refresh_recent()

        undo = QAction("Undo last rename", m)
        undo.triggered.connect(self.undo_last)
        m.addAction(undo)

        organize = QAction("Organize Downloads now…", m)
        organize.triggered.connect(self.organize_now)
        m.addAction(organize)

        open_folder = QAction("Open Downloads folder", m)
        open_folder.triggered.connect(lambda: self._reveal(self.folder, select=False))
        m.addAction(open_folder)
        m.addSeparator()

        prefix = QAction("Add date prefix (26-11 …)", m, checkable=True)
        prefix.setChecked(bool(_setting(self.settings, "watcher_date_prefix")))
        prefix.toggled.connect(lambda v: self.settings.set("watcher_date_prefix", v))
        m.addAction(prefix)

        smart = QAction("Smart project folders (like a human)", m, checkable=True)
        smart.setChecked(bool(_setting(self.settings, "watcher_smart_folders")))
        smart.toggled.connect(lambda v: self.settings.set("watcher_smart_folders", v))
        m.addAction(smart)

        folders = QAction("Sort into type folders (Documents, Images…)", m, checkable=True)
        folders.setChecked(bool(_setting(self.settings, "watcher_type_folders")))
        folders.toggled.connect(lambda v: self.settings.set("watcher_type_folders", v))
        m.addAction(folders)

        self.autostart_action = QAction("Start when the computer starts", m, checkable=True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.toggled.connect(self._toggle_autostart)
        m.addAction(self.autostart_action)

        settings_action = QAction("Open BeeOrganizer (settings, OpenAI key)…", m)
        settings_action.triggered.connect(self.open_window)
        m.addAction(settings_action)
        m.addSeparator()

        quit_action = QAction("Quit BeeOrganizer", m)
        quit_action.triggered.connect(self.quit)
        m.addAction(quit_action)

    def _status_text(self) -> str:
        if self.watcher.paused:
            return "⏸ Paused"
        return f"● Watching {self.folder.name}"

    def _refresh_recent(self) -> None:
        self.recent_menu.clear()
        if not self.recent:
            a = self.recent_menu.addAction("Nothing yet")
            a.setEnabled(False)
            return
        for r in self.recent:
            label = f"{r.get('original_name')}  →  {r.get('new_name')}"
            a = self.recent_menu.addAction(label)
            a.triggered.connect(lambda _=False, p=r.get("new_path"): self._reveal(Path(p)))

    def _on_event(self, result: Dict) -> None:
        status = result.get("status")
        if status in ("RENAMED", "ORGANIZED"):
            self.recent.insert(0, result)
            del self.recent[RECENT_LIMIT:]
            self._refresh_recent()
            if result.get("is_folder"):
                self.tray.showMessage(
                    "Folder organized",
                    f"{result.get('original_name')}\n→ {result.get('new_name')} ({result.get('moved', 0)} items)",
                    QSystemTrayIcon.MessageIcon.Information, 6000)
            else:
                where = result.get("placed_in") or result.get("subfolder")
                shown = (f"{where}/" if where else "") + result.get("new_name", "")
                self.tray.showMessage("Download organized" if result.get("placed_in") else "Download renamed",
                                      f"{result.get('original_name')}\n→ {shown}",
                                      QSystemTrayIcon.MessageIcon.Information, 5000)
        elif status == "ERROR":
            self.tray.showMessage("Could not rename", f"{result.get('original_name')}: {result.get('message')}",
                                  QSystemTrayIcon.MessageIcon.Warning, 5000)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            if sys.platform.startswith("win"):
                self.open_window()

    def _toggle_pause(self, paused: bool) -> None:
        self.watcher.pause(paused)
        self.status_action.setText(self._status_text())

    def _toggle_autostart(self, on: bool) -> None:
        if on == autostart.is_enabled():
            return
        try:
            autostart.enable() if on else autostart.disable()
        except Exception as e:
            QMessageBox.warning(None, "BeeOrganizer", f"Could not change start-up setting:\n{e}")
            self.autostart_action.setChecked(autostart.is_enabled())

    def _first_run(self) -> None:
        if _setting(self.settings, "autostart_asked"):
            return
        self.settings.set("autostart_asked", True)
        if not autostart.is_enabled():  # the Windows installer already turns it on
            answer = QMessageBox.question(
                None, "BeeOrganizer",
                "Start BeeOrganizer automatically when the computer starts?\n\n"
                f"It will watch {self.folder} and rename every new download.",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.autostart_action.setChecked(True)
        if not (self.settings.get("openai_api_key", "") or "").strip():
            self.tray.showMessage(
                "Add your OpenAI key for exact names",
                "Open BeeOrganizer → Settings → OpenAI Precise Titles.",
                QSystemTrayIcon.MessageIcon.Information, 8000,
            )

    def undo_last(self) -> None:
        last = next((r for r in self.recent if r.get("session_ids") or r.get("session_id")), None)
        if not last:
            self.tray.showMessage("Nothing to undo", "No rename in this session yet.")
            return
        # Restored names must not be picked up again as "new downloads"
        for name in (last.get("original_name"), last.get("new_name"),
                     Path(last.get("new_path") or "x").name):
            if name:
                self.watcher.ignore(name)
        sessions = last.get("session_ids") or [last["session_id"]]
        processor = DownloadProcessor()
        results = [processor.undo(sid) for sid in reversed(sessions)]
        self.recent.remove(last)
        self._refresh_recent()
        ok = all(r.get("status") == "REVERTED" for r in results)
        self.tray.showMessage("Undone" if ok else "Undo partly failed",
                              "; ".join(r.get("message", "") for r in results)[:250])

    # ---- Organize Downloads now ----------------------------------------------------
    def organize_now(self) -> None:
        if self._organizing:
            self.tray.showMessage("BeeOrganizer", "Already organizing, please wait…")
            return
        self._organizing = True
        self.tray.showMessage("BeeOrganizer", "Reading your Downloads to plan the organization…")

        def work():
            try:
                plan = SmartOrganizer(self.folder).plan_downloads()
            except Exception as e:
                logger.exception("Organize plan failed")
                plan = e
            self.bridge.plan_ready.emit(plan)

        threading.Thread(target=work, daemon=True).start()

    def _confirm_plan(self, plan) -> None:
        if isinstance(plan, Exception):
            self._organizing = False
            QMessageBox.warning(None, "BeeOrganizer", f"Could not plan the organization:\n{plan}")
            return
        if not plan.moves:
            self._organizing = False
            QMessageBox.information(None, "BeeOrganizer",
                                    f"Your Downloads already look organized.\n\n{plan.explanation}")
            return
        box = QMessageBox(QMessageBox.Icon.Question, "Organize Downloads",
                          f"{plan.summary()}\n\n{plan.explanation}\n\nApply? You can undo it from the menu.",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDetailedText(plan.details(200))
        if box.exec() != QMessageBox.StandardButton.Yes:
            self._organizing = False
            return

        def work():
            self.watcher.pause(True)
            try:
                result = SmartOrganizer(self.folder).apply(plan, label="Organize Downloads")
                for f in result.get("folders", []):
                    self.watcher.ignore(Path(f).name)
                for mv in plan.moves:
                    self.watcher.ignore(mv.src.name)
            finally:
                self.watcher.pause(False)
            result.update(is_folder=True, original_name="Downloads",
                          new_name=f"{len(result.get('folders', []))} folders",
                          session_ids=[result["session_id"]] if result.get("session_id") else [])
            self.bridge.organize_done.emit(result)

        threading.Thread(target=work, daemon=True).start()

    def _on_organized(self, result: Dict) -> None:
        self._organizing = False
        self._on_event(result)

    def open_window(self) -> None:
        from src.app.main_window import MainWindow
        if self.window is None:
            self.window = MainWindow()
            if ICON_PATH.exists():
                self.window.setWindowIcon(QIcon(str(ICON_PATH)))
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    @staticmethod
    def _reveal(path: Path, select: bool = True) -> None:
        from src.integrations.native_host import _reveal
        try:
            _reveal(str(path), select=select)
        except Exception as e:
            logger.warning("Cannot open %s: %s", path, e)

    def quit(self) -> None:
        self.watcher.stop()
        self.tray.hide()
        self.app.quit()


def run(show_window: bool = False) -> int:
    """Start background mode. Returns the exit code."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("BeeOrganizer")
    app.setQuitOnLastWindowClosed(False)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    lock = QLockFile(str(get_app_data_dir() / "beeorganizer_watcher.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        # Already running in the background: just open the window if asked.
        if show_window:
            from src.app.main_window import MainWindow
            w = MainWindow()
            w.show()
            app.setQuitOnLastWindowClosed(True)
            return app.exec()
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "BeeOrganizer", "No system tray / menu bar is available on this system.")
        return 1

    controller = TrayController(app, show_window=show_window)  # noqa: F841 (kept alive)
    app._bee_controller = controller
    app._bee_lock = lock
    return app.exec()
