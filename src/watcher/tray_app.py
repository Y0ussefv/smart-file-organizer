"""
BeeOrganizer background mode: an icon near the clock (Windows) / in the menu bar (macOS)
that watches the Downloads folder and runs the V2 pipeline on every new download
(src/bee/pipeline.py): local privacy check, exact name, filing only into approved
projects when the evidence is strong, otherwise a proposal or the file stays in Downloads.

    SmartFileOrganizer.exe --watch        (or: python main.py --watch)
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QLockFile, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from src.bee.ledger import Ledger
from src.bee.pipeline import BeePipeline
from src.storage.settings import SettingsManager
from src.utils.platform_utils import get_app_data_dir, get_downloads_dir
from src.watcher import autostart
from src.watcher.download_watcher import DownloadWatcher

logger = logging.getLogger("SmartFileOrganizer")

ICON_PATH = Path(__file__).resolve().parents[1] / "app" / "assets" / "icon.png"
RECENT_LIMIT = 10

DEFAULTS = {
    "watcher_date_prefix": True,     # "26-11 Title.pdf"
    "autostart_asked": False,
    "projects_root": "",             # default: <Downloads>/Projets
    "openai_model": "gpt-5-mini",
}


def _setting(settings: SettingsManager, key: str):
    return settings.get(key, DEFAULTS[key])


class _Bridge(QObject):
    """Carries watcher events from the worker thread to the Qt (GUI) thread."""
    event = Signal(dict)


class TrayController(QObject):
    def __init__(self, app: QApplication, show_window: bool = False):
        super().__init__()
        self.app = app
        self.settings = SettingsManager()
        self.recent: List[Dict] = []
        self.window = None
        self.folder = Path(self.settings.get("watch_folder", "") or get_downloads_dir())

        self.ledger = Ledger()
        root = _setting(self.settings, "projects_root") or str(self.folder / "Projets")
        self.pipeline = BeePipeline(
            self.folder, Path(root), ledger=self.ledger,
            api_key_provider=lambda: SettingsManager().get("openai_api_key", ""),
            model=_setting(self.settings, "openai_model") or "gpt-5-mini")
        try:
            self.pipeline.recover()  # T17: settle anything interrupted by a crash or shutdown
        except Exception:
            logger.exception("Recovery failed")

        self.bridge = _Bridge()
        self.bridge.event.connect(self._on_event)
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
        settings = SettingsManager()  # re-read: picks up option changes
        self.pipeline.date_prefix = bool(_setting(settings, "watcher_date_prefix"))
        self.pipeline.model = _setting(settings, "openai_model") or "gpt-5-mini"
        return self.pipeline.process_new_item(path)

    def _process_dir(self, path: Path) -> Dict:
        # A received folder keeps its structure: unwrapping, merging or splitting it
        # needs a preview and the user's consent (spec V2 §5.3), so nothing happens here.
        return {"status": "SKIPPED", "original_name": path.name, "new_name": path.name,
                "message": "Folder left as it is"}

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

        self.proposals_action = QAction(self._proposals_text(), m)
        self.proposals_action.triggered.connect(self.open_proposals)
        m.addAction(self.proposals_action)

        projects = QAction("Projects…", m)
        projects.triggered.connect(self.open_projects)
        m.addAction(projects)

        privacy = QAction("Privacy and cloud analysis…", m)
        privacy.triggered.connect(self.open_privacy)
        m.addAction(privacy)

        open_folder = QAction("Open Downloads folder", m)
        open_folder.triggered.connect(lambda: self._reveal(self.folder, select=False))
        m.addAction(open_folder)
        m.addSeparator()

        prefix = QAction("Add date prefix (26-11 …)", m, checkable=True)
        prefix.setChecked(bool(_setting(self.settings, "watcher_date_prefix")))
        prefix.toggled.connect(lambda v: self.settings.set("watcher_date_prefix", v))
        m.addAction(prefix)

        self.autostart_action = QAction("Start when the computer starts", m, checkable=True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.toggled.connect(self._toggle_autostart)
        m.addAction(self.autostart_action)

        settings_action = QAction("Open BeeOrganizer…", m)
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

    def _proposals_text(self) -> str:
        n = len(self.ledger.proposals())
        return f"Proposals ({n})…" if n else "Proposals…"

    def _on_event(self, result: Dict) -> None:
        status = result.get("status")
        self.proposals_action.setText(self._proposals_text())
        # PR-19: no names of confidential documents in system notifications
        hidden = bool(result.get("confidential"))
        before = "a confidential document" if hidden else result.get("original_name", "")
        after = "(name hidden: confidential)" if hidden else result.get("new_name", "")
        if status in ("RENAMED", "FILED") or result.get("proposal_id") or result.get("new_project_proposal"):
            if result.get("batch_id") and status in ("RENAMED", "FILED"):
                self.recent.insert(0, result)
                del self.recent[RECENT_LIMIT:]
                self._refresh_recent()
            if status == "FILED":
                title, body = "Download filed", f"{before}\n→ {result.get('placed_in')}/{after}"
            elif result.get("proposal_id"):
                title = "Download renamed"
                body = f"{after}\nSuggested project: {result.get('proposed_project')} (see Proposals)"
            else:
                title, body = "Download renamed", f"{before}\n→ {after}"
            if result.get("new_project_proposal"):
                body += "\nNew project suggested (see Proposals)"
            self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 5000)
        elif status == "ERROR":
            self.tray.showMessage("Not processed", f"{before}: {result.get('message')}",
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

    def undo_last(self) -> None:
        last = self.recent[0] if self.recent else None
        if not last:
            self.tray.showMessage("Nothing to undo", "No change in this session yet.")
            return
        # Restored names must not be picked up again as "new downloads"
        for name in (last.get("original_name"), last.get("new_name")):
            if name:
                self.watcher.ignore(name)
        result = self.pipeline.undo(last["batch_id"])
        self.recent.remove(last)
        self._refresh_recent()
        msg = "; ".join(result.get("notes", []) + result.get("errors", [])) or "Name and place restored."
        self.tray.showMessage("Undone" if result["status"] == "REVERTED" else "Undo partly done", msg[:250])

    def _with_watcher_paused(self, fn):
        """User-approved moves: pause the watcher so our own changes are not new downloads."""
        was = self.watcher.paused
        self.watcher.pause(True)
        try:
            return fn()
        finally:
            if self.folder.exists():
                for p in self.folder.iterdir():
                    self.watcher.ignore(p.name)
            self.watcher.pause(was)

    def open_proposals(self) -> None:
        from src.bee.ui import ProposalsDialog
        ProposalsDialog(self.pipeline, run=self._with_watcher_paused).exec()
        self.proposals_action.setText(self._proposals_text())

    def open_projects(self) -> None:
        from src.bee.ui import ProjectsDialog
        ProjectsDialog(self.pipeline).exec()

    def open_privacy(self) -> None:
        from src.bee.ui import PrivacyDialog
        PrivacyDialog(self.pipeline, SettingsManager()).exec()

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
        from src.utils.platform_utils import reveal_in_file_manager
        try:
            reveal_in_file_manager(path, select=select)
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
