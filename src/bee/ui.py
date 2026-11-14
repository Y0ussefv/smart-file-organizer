"""
V2 windows opened from the tray menu (spec §9.1, §10.5):

    ProposalsDialog  pending suggestions: file -> project, new project (preview before anything moves)
    ProjectsDialog   approved project catalog: create, aliases, references, "always local", categories
    PrivacyDialog    cloud analysis switch (off by default) with the information to read first,
                     OpenAI key in the system vault, purge of the local history
"""

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextBrowser,
                               QVBoxLayout)

from src.bee.ledger import PRIVACY_INFO_VERSION
from src.bee.mover import MoveRefused
from src.bee.pipeline import BeePipeline, folder_name


def _split(text: str):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


# ---------------------------------------------------------------------------------------------
class ProposalsDialog(QDialog):
    def __init__(self, pipeline: BeePipeline, run: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.run = run or (lambda fn: fn())
        self.setWindowTitle("BeeOrganizer – Proposals")
        self.resize(720, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Nothing moves until you accept. Refused proposals leave the files where they are."))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)
        lay.addWidget(self.list)
        self.details = QTextBrowser()
        lay.addWidget(self.details)
        row = QHBoxLayout()
        for label, fn in (("Accept", self._accept), ("Choose another project…", self._other),
                          ("Leave in Downloads", self._refuse)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self._load()

    def _load(self):
        self.items = self.pipeline.ledger.proposals()
        self.list.clear()
        for p in self.items:
            d = p["payload"]
            if p["kind"] == "file_move":
                text = f"File → {d['project']}:  {d['name']}"
            else:
                text = f"New project “{d['name']}”: {len(d['files'])} files"
            self.list.addItem(text)
        if self.items:
            self.list.setCurrentRow(0)
        else:
            self.details.setPlainText("No pending proposal.")

    def _current(self):
        row = self.list.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def _show(self, _row):
        p = self._current()
        if not p:
            return
        d = p["payload"]
        root = self.pipeline.projects_root
        if p["kind"] == "file_move":
            project = self.pipeline.ledger.project(d["project_id"])
            self.details.setPlainText(
                f"Current file:  {d['name']}\n"
                f"Proposed project:  {d['project']}\n"
                f"Destination:  {project.path if project else '?'}\n\n"
                f"Why: {d['reason']}\nEvidence: {', '.join(d['evidence']) or '-'}\n"
                f"Contradictions: {', '.join(d['contradictions']) or 'none'}")
        else:
            files = "\n".join(f"  • {f['name']}" for f in d["files"])
            self.details.setPlainText(
                f"Create the project folder:\n  {d['target']}\n\nand move these {len(d['files'])} files into it:\n"
                f"{files}\n\nEffect: 1 new folder in {root}. Nothing else changes. You can undo it.")

    def _done(self, out):
        if out.get("status") == "ERROR":
            QMessageBox.warning(self, "BeeOrganizer", out.get("message", "Failed"))
        self._load()

    def _accept(self):
        p = self._current()
        if p:
            try:
                self._done(self.run(lambda: self.pipeline.accept_proposal(p["proposal_id"])))
            except (MoveRefused, OSError) as e:
                QMessageBox.warning(self, "BeeOrganizer", f"Nothing was moved: {e}")
                self._load()

    def _other(self):
        p = self._current()
        if not p or p["kind"] != "file_move":
            return
        projects = self.pipeline.ledger.projects()
        names = [x.name for x in projects]
        name, ok = QInputDialog.getItem(self, "Choose a project", "Project:", names, 0, False)
        if ok and name:
            pid = projects[names.index(name)].project_id
            self._done(self.run(lambda: self.pipeline.accept_proposal(p["proposal_id"], project_id=pid)))

    def _refuse(self):
        p = self._current()
        if p:
            self.pipeline.refuse_proposal(p["proposal_id"])
            self._load()


# ---------------------------------------------------------------------------------------------
class ProjectsDialog(QDialog):
    def __init__(self, pipeline: BeePipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.setWindowTitle("BeeOrganizer – Projects")
        self.resize(640, 440)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Approved projects (folders in {pipeline.projects_root}). A document is filed "
                             "automatically only with a strong, specific match: the project name or one of its "
                             "references, and no contradiction."))
        self.list = QListWidget()
        lay.addWidget(self.list)
        row = QHBoxLayout()
        for label, fn in (("New project…", self._new), ("Edit…", self._edit), ("Add category…", self._category),
                          ("Archive", self._archive)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self._load()

    def _load(self):
        self.projects = self.pipeline.ledger.projects()
        self.list.clear()
        for p in self.projects:
            cats = ", ".join(c.name for c in self.pipeline.ledger.categories(p.project_id))
            flags = "  🔒 always local" if p.always_local else ""
            extra = f"  | aliases: {', '.join(p.aliases)}" if p.aliases else ""
            extra += f"  | refs: {', '.join(p.refs)}" if p.refs else ""
            extra += f"  | categories: {cats}" if cats else ""
            self.list.addItem(f"{p.name}{flags}{extra}")

    def _current(self):
        row = self.list.currentRow()
        return self.projects[row] if 0 <= row < len(self.projects) else None

    def _form(self, title, project=None):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        name = QLineEdit(project.name if project else "")
        aliases = QLineEdit(", ".join(project.aliases) if project else "")
        refs = QLineEdit(", ".join(project.refs) if project else "")
        excl = QLineEdit(", ".join(project.exclusions) if project else "")
        local = QCheckBox("Always local (never any cloud call for this project's files)")
        local.setChecked(bool(project and project.always_local))
        form.addRow("Name", name)
        form.addRow("Aliases (comma)", aliases)
        form.addRow("References / mission ids", refs)
        form.addRow("Exclusions (comma)", excl)
        form.addRow(local)
        ok = QPushButton("Save")
        ok.clicked.connect(dlg.accept)
        form.addRow(ok)
        if project:
            name.setEnabled(False)  # the folder keeps its name; aliases enrich the project (§8)
        if dlg.exec() != QDialog.DialogCode.Accepted or not name.text().strip():
            return None
        return name.text().strip(), _split(aliases.text()), _split(refs.text()), _split(excl.text()), local.isChecked()

    def _new(self):
        data = self._form("New project")
        if data:
            name, aliases, refs, excl, local = data
            target = self.pipeline.projects_root / folder_name(name)
            if QMessageBox.question(self, "New project", f"Create the project “{name}”?\n\nIts folder will be\n"
                                    f"{target}\n(created only when the first file is filed).") \
                    == QMessageBox.StandardButton.Yes:
                self.pipeline.create_project(name, aliases, refs, excl, local)
                self._load()

    def _edit(self):
        p = self._current()
        if p:
            data = self._form("Edit project", p)
            if data:
                _, aliases, refs, excl, local = data
                if p.always_local and not local:
                    if QMessageBox.question(self, "Always local", "Allow cloud analysis again for this project's "
                                            "public (P0) documents?") != QMessageBox.StandardButton.Yes:
                        local = True
                self.pipeline.ledger.update_project(p.project_id, aliases=aliases, refs=refs,
                                                    exclusions=excl, always_local=local)
                self._load()

    def _category(self):
        p = self._current()
        if not p:
            return
        name, ok = QInputDialog.getText(self, "Add category", f"Category inside {p.name} (e.g. Contrats, Rapports):")
        if ok and name.strip():
            target = Path(p.path) / folder_name(name)
            if QMessageBox.question(self, "Add category", f"Approve the category folder\n{target}\n\nDocuments go "
                                    "there automatically only when they clearly belong to the project AND to "
                                    "this category. No deeper folder is ever created.") \
                    == QMessageBox.StandardButton.Yes:
                try:
                    self.pipeline.add_category(p.project_id, name.strip(), [name.strip()])
                except MoveRefused as e:
                    QMessageBox.warning(self, "BeeOrganizer", str(e))
                self._load()

    def _archive(self):
        p = self._current()
        if p and QMessageBox.question(self, "Archive", f"Stop filing documents into {p.name}? Its folder stays.") \
                == QMessageBox.StandardButton.Yes:
            self.pipeline.ledger.update_project(p.project_id, status="archived")
            self._load()


# ---------------------------------------------------------------------------------------------
PRIVACY_TEXT = f"""
<h3>Cloud analysis (OpenAI) – off by default</h3>
<p><b>Without it, BeeOrganizer works fully on this computer:</b> watching, naming, projects, history and Undo.</p>
<p><b>Purpose.</b> Only to find a more precise file name.</p>
<p><b>What can be sent.</b> For a document classified <b>P0 (public / low risk)</b> by the local check, and
only then: a short redacted excerpt of its text (e-mails, phone numbers, IBANs, identifiers, long numbers,
links and paths removed) and the file extension. <b>Never</b> the file itself, its name, its folder, its images,
video frames or metadata.</p>
<p><b>Never sent.</b> Documents classified P1 (confidential / personal: invoices, contracts, CVs, contact
details…), P2 (very sensitive: passports, residence permits, health, criminal records, national numbers…) or
INCONNU (unreadable, scanned, images, videos, archives), and every file of a project marked “always local”.
These rules cannot be overridden from the app.</p>
<p><b>Provider.</b> OpenAI (API), possibly outside the EEA. The request asks not to store the completion
(<code>store=false</code>), but OpenAI may keep API data up to 30 days for abuse monitoring, with exceptions.
Check your organisation's agreement (DPA) with OpenAI before turning this on.</p>
<p><b>Important.</b> Turning this on is your choice for your files; it is not the GDPR consent of the people
named in your documents.</p>
<p><b>Turning it off</b> stops every new request immediately. Data already received by the provider follows
the provider's rules.</p>
<p><small>Information version {PRIVACY_INFO_VERSION}</small></p>
"""


class PrivacyDialog(QDialog):
    def __init__(self, pipeline: BeePipeline, settings, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.settings = settings
        self.setWindowTitle("BeeOrganizer – Privacy")
        self.resize(640, 620)
        lay = QVBoxLayout(self)
        info = QTextBrowser()
        info.setHtml(PRIVACY_TEXT)
        lay.addWidget(info)

        self.read = QCheckBox("I have read this information")
        self.cloud = QCheckBox("Cloud analysis of public (P0) documents with OpenAI")
        self.cloud.setChecked(pipeline.ledger.cloud_enabled())
        self.read.setChecked(self.cloud.isChecked())
        self.cloud.setEnabled(self.read.isChecked())
        self.read.toggled.connect(self.cloud.setEnabled)
        lay.addWidget(self.read)
        lay.addWidget(self.cloud)

        form = QFormLayout()
        self.key = QLineEdit(settings.get("openai_api_key", ""))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-…  (stored in the system vault, never in a file)")
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems(["gpt-5-mini", "gpt-5", "gpt-4.1-mini"])
        self.model.setCurrentText(settings.get("openai_model", "gpt-5-mini") or "gpt-5-mini")
        form.addRow("OpenAI API key", self.key)
        form.addRow("Model", self.model)
        lay.addLayout(form)

        lay.addWidget(QLabel("Local history: technical events are kept 30 days, Undo history 90 days, "
                             "then purged automatically. No document text is ever stored."))
        row = QHBoxLayout()
        purge = QPushButton("Purge history now")
        purge.clicked.connect(self._purge)
        row.addWidget(purge)
        row.addStretch()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        row.addWidget(save)
        lay.addLayout(row)

    def _purge(self):
        if QMessageBox.question(self, "Purge", "Delete the local history (events, decisions, Undo)? "
                                "Projects and your files are not touched. Undo will no longer be possible "
                                "for past changes.") == QMessageBox.StandardButton.Yes:
            self.pipeline.ledger.purge_all_history()

    def _save(self):
        if not self.settings.set("openai_api_key", self.key.text().strip()):
            QMessageBox.warning(self, "API key not saved",
                                "The system's secure vault is not available, so the key was not saved.")
        self.settings.set("openai_model", self.model.currentText().strip() or "gpt-5-mini")
        self.pipeline.set_cloud(self.cloud.isChecked() and self.read.isChecked())
        self.accept()
