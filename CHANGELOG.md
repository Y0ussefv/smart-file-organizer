# Changelog

All notable changes to the **Smart File Organizer & Intelligent File Renamer** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-11-08

### Fixed
- Chrome / Edge showed **"Virus scan failed"** on downloads: BeeOrganizer renamed the file while Windows Defender was still scanning it. It now waits until no other program has the file open, and waits 6 s (was 3 s) after the download stops growing.

## [1.4.0] - 2026-11-08

### Added
- **Smart project folders** (`src/organizer/smart_organizer.py`): new folders in Downloads are unwrapped (`folderX/folderY/FILES` → `folderX/FILES`) and arranged like a human would. Project folder from the content, subfolders only when useful (`Project Delfa/Contact`, `Project Delfa/Assets`), exact file names, and merging into an existing project. Software projects are only unwrapped.
- New single files are filed into the matching existing project folder.
- **Organize Downloads now…** tray action: previews the plan, applies on confirmation, and can be undone as one step.
- Undo recreates folders removed during organizing and cleans up emptied ones.

## [1.3.0] - 2026-11-07

### Added
- **Professional Windows install**: `BeeOrganizer.exe` with name, publisher (RNJ), version and icon embedded; `BeeOrganizer-Setup.exe` (Inno Setup, English and French, no admin rights) with Start menu and Desktop shortcuts, start-up entry, and an Installed apps entry with Uninstall.
- **Release pipeline** (`.github/workflows/release.yml`): builds the Windows Setup and macOS `.dmg` (Apple Silicon + Intel) for each GitHub Release, and is ready for free SignPath code signing (`docs/SIGNING.md`).
- **Background mode (BeeOrganizer)**: the app runs in the system tray / menu bar, starts with the computer (Windows Run key, macOS LaunchAgent, Linux autostart), watches the Downloads folder and renames every new download from any app with a `YY-MM ` prefix (`26-11 Title.pdf`). Includes pause, recent renames, undo last, and type folders. `--watch` / `--no-watch` flags.
- BeeOrganizer 2.1: reads PDFs and other files generated inside web pages (`blob:` downloads) through the page's tab, so they're renamed too instead of being skipped.
- **BeeOrganizer browser extension v2 (Chrome / Edge / Brave)** in `browser_extension/`: standalone, with no Python needed. When a download starts, it reads the file in memory (PDF, Office, images, text, zip) and asks OpenAI for an exact title, so Chrome saves it directly under that name. Options: name style, folder per website/type, size limit, skip list. Private zip to share: `python build_scripts/package_extension.py` (dist/BeeOrganizer.zip); store zip: add `--store`.
- (Optional, not used by extension v2) Native messaging bridge (`src/integrations/native_host.py`) and installer (`python main.py --install-browser-bridge`) for Windows, macOS and Linux.
- `DownloadProcessor` for single-file analyze → collision-safe rename → undo history.
- **OpenAI Precise Titles** (`src/core/openai_titler.py`): when an OpenAI key is set (Settings or `OPENAI_API_KEY`), every file's real content (text, slides, sheets, images, video keyframes, archive listings) is sent to OpenAI, which returns an exact 3–10 word title using only names, numbers and dates found in the file. Runs 6 files in parallel; falls back to local analysis on errors.

## [1.0.0] - 2026-10-19

### Added
- **Modern PySide6 GUI**:
  - Interactive Dashboard with folder selection, recursive subfolder toggle, and live status progress.
  - KPI summary cards displaying Total Scanned, Supported, Unsupported, Ready to Rename, Unchanged, and Error metrics.
  - Dynamic Light and Dark themes with modern Catppuccin-inspired palettes, smooth pill badges, and typography.
  - Interactive File Preview Table supporting in-place editing of proposed filenames, per-file inclusion checkboxes, search filtering, status filtering, and file-type filtering.
  - Collapsible real-time Activity Log.
- **Intelligent File Extractors**:
  - `PDFExtractor`: Extracts metadata (Title, Author, Subject) and first-page headings with encrypted PDF detection using `pypdf`.
  - `DocxExtractor`: Extracts Word styles (Title, Heading 1/2) and opening paragraphs using `python-docx`.
  - `XlsxExtractor`: Inspects workbook properties, sheet names, and table headers using `openpyxl`.
  - `PptxExtractor`: Extracts presentation titles and first slide headings using `python-pptx`.
  - `TextExtractor`: Safe chunked extraction for TXT, Markdown, CSV, JSON, XML, HTML, and YAML.
  - `SourceCodeExtractor`: Inspects docstrings, comments, and top-level class/function definitions across Python, JS/TS, Java, C/C++, C#, Go, Rust, and SQL.
  - `ImageExtractor`: Inspects EXIF metadata (ImageDescription, XPTitle, DateTimeOriginal, camera model) using `Pillow`.
  - `ArchiveExtractor`: Inspects ZIP and TAR archives without extracting files.
  - `FallbackExtractor`: Conservative fallback that preserves original filenames for unhandled binary formats.
- **Safe Renaming & Collision Engine**:
  - Strict zero-overwrite guarantee: detects existing filesystem collisions and batch-internal collisions.
  - Deterministic suffixing (`_2`, `_3`, etc.) for unique target naming.
  - Atomic rename operations (`os.replace` / `Path.rename`) with post-rename existence and file size validation.
  - Safe cancellation support at any point without leaving files in an inconsistent state.
- **Full Undo Operation**:
  - SQLite persistent history tracking every session and file rename with SHA-256 hashes and timestamps.
  - Reversible rename session manager that verifies file availability and prevents overwriting existing destination files.
- **Comprehensive Reporting**:
  - Automatic generation of Excel-compatible CSV reports (UTF-8 with BOM `utf-8-sig`).
  - Human-readable TXT summary audit reports.
  - Structured machine-readable JSON reports.
  - One-click native folder opener for exported reports.
- **Cross-Platform Distribution**:
  - Standalone PyInstaller specification (`smart_file_organizer.spec`).
  - Automated build scripts for Windows (`build_windows.bat`), macOS (`build_macos.sh`), and Linux (`build_linux.sh`).
- **Automated Test Suite**:
  - 40 automated tests covering sanitization, collisions, extractors, scanner, renaming, undo, reports, storage, and offscreen GUI interactions.
