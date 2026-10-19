# System Architecture & Technical Specifications

**Smart File Organizer & Intelligent File Renamer** is architected as a modular, thread-safe, cross-platform desktop application built using Python and PySide6 (Qt).

---

## 1. High-Level Component Architecture

```
[ PySide6 Desktop GUI (src/app/) ]
       │
       ├── Dashboard & KPI Stats (stats_widget.py)
       ├── Interactive Preview Table (preview_table.py)
       ├── Theme & Stylesheets (theme.py)
       └── Modals & Dialogs (dialogs.py)
              │
              ▼ [Qt Signals & Slots]
[ Asynchronous Worker Threads (QThread) ]
       │
       ├── DirectoryScanner (src/core/scanner.py)
       ├── RenameEngine (src/core/rename_engine.py)
       └── UndoManager (src/core/undo_manager.py)
              │
              ▼
[ Core Domain & Processing Layer (src/core/) ]
       ├── FileClassifier (file_classifier.py)
       ├── Content Extractors (content_extractors.py)
       │      ├── PDFExtractor (pypdf)
       │      ├── DocxExtractor (python-docx)
       │      ├── XlsxExtractor (openpyxl)
       │      ├── PptxExtractor (python-pptx)
       │      ├── TextExtractor (chunked text, json, md, csv, html, svg, url, tex, yaml, toml)
       │      ├── SourceCodeExtractor (docstrings, classes, shaders, modern languages)
       │      ├── ImageExtractor (Pillow EXIF, Google AI Gemini Vision)
       │      ├── ExecutableExtractor (pefile, vsix manifest, msi)
       │      ├── MediaExtractor (wave, ID3 audio tags, video containers)
       │      ├── FontExtractor (pure-Python OpenType/TrueType name table parser)
       │      ├── ArchiveExtractor (zipfile, tarfile)
       │      └── UniversalFallbackExtractor (100% universal format support)
       ├── TitleGenerator (title_generator.py)
       ├── FilenameSanitizer (filename_sanitizer.py)
       └── CollisionHandler (collision_handler.py)
              │
              ▼
[ Storage & Reporting Layer ]
       ├── HistoryManager (src/storage/history.py - SQLite)
       ├── SettingsManager (src/storage/settings.py - JSON)
       └── ReportManager (src/reports/ - CSV, TXT, JSON)
```

---

## 2. Key Design Principles

### Non-Destructive Operation & Zero Overwrite Guarantee
- The application **never overwrites** an existing file.
- Collisions are detected both against disk files and in-batch duplicate proposals.
- Unique deterministic suffixes (`_2`, `_3`, etc.) are assigned automatically.
- No original files or file contents are ever deleted.

### Content-Aware Descriptive Naming
- Prefers document titles, headings, and metadata over original filenames.
- Natural language heuristics strip generic boilerplate (e.g. "Page 1 of 10", URLs, email addresses, "untitled").
- Conservative safety: if no meaningful title can be extracted, the original filename is safely retained and explained in the audit log.

### Cross-Platform Compliance
- **Windows**: Sanitizes prohibited characters (`< > : " / \ | ? *`), handles reserved names (`CON, PRN, AUX, NUL, COM1-9, LPT1-9`), and trims trailing dots and spaces.
- **POSIX (Linux/macOS)**: Replaces `/` and null bytes.
- **Compound Extensions**: Preserves compound extensions such as `.tar.gz`, `.tar.bz2`, `.spec.ts`, `.d.ts`.
- **Unicode Support**: Normalizes characters using Unicode NFC normalization, preserving accented and non-Latin character sets (French, German, Spanish, Japanese, Chinese, Cyrillic, Arabic).

### Memory Safety & Streaming Hashing
- Text extractors read at most 1 MB chunks to prevent memory exhaustion on gigabyte-sized files.
- SHA-256 calculation streams data in 64 KB chunks up to a safe threshold.
- Archive extractors inspect file listings without extracting archive contents to disk.

### Fully Reversible Renaming (Undo)
- Each rename session is saved to an audit table in SQLite (`history.sqlite3`).
- Reversals verify that the renamed file still exists and that the original destination is unoccupied before attempting to restore.

---

## 3. Storage & Directory Locations

Application data, logs, and default reports are stored in standard platform user directories:
- **Windows**: `%APPDATA%\SmartFileOrganizer`
- **macOS**: `~/Library/Application Support/SmartFileOrganizer`
- **Linux**: `~/.local/share/SmartFileOrganizer` or `$XDG_DATA_HOME/SmartFileOrganizer`
