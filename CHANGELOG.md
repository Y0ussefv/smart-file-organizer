# Changelog

All notable changes to the **Smart File Organizer & Intelligent File Renamer** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
