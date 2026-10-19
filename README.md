# Smart File Organizer & Intelligent File Renamer

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-green.svg)](https://wiki.qt.io/Qt_for_Python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/Tests-58%20Passed-brightgreen.svg)]()

**Smart File Organizer** is a desktop application that scans directories, reads document contents and metadata, generates concise descriptive filenames, renames files safely, and produces detailed audit reports (CSV, TXT, JSON).

It runs on **Windows, macOS, and Linux** with a graphical interface requiring zero terminal commands for normal use.

---

## 🌟 Key Features

- **Content-Aware Descriptive Filename Generation**:
  - Analyzes actual document titles, headings, and internal properties instead of generic numbers or ambiguous camera labels.
  - Examples:
    - `document_8392.pdf` ➔ `CI_CD_Deployment_Guide.pdf`
    - `file_final_v2.docx` ➔ `Professional_Internship_Report.docx`
    - `source123.py` ➔ `API_Authentication_Module.py`
    - `budget_raw.xlsx` ➔ `Q3_Financial_Summary.xlsx`
    - `slides_draft.pptx` ➔ `Product_Launch_Roadmap.pptx`
- **Modern PySide6 GUI**:
  - Native folder picker with subfolder recursion toggle.
  - KPI summary metric cards (Total Scanned, Supported, Ready to Rename, Unchanged, Errors).
  - Dark Mode and Light Mode with modern typography, glassmorphism hints, and status badge styling.
  - Interactive Preview Table with in-place filename editing, inclusion checkboxes, multi-column sorting, and real-time search/status filtering.
  - Collapsible Activity Log tracking real-time events.
- **Strict Data Safety & Zero Overwrite Guarantee**:
  - Never overwrites existing files.
  - Detects naming collisions before renaming and generates deterministic suffixes (`_2`, `_3`, etc.).
  - Atomic rename operations with post-rename existence and file size verification.
  - Per-file error isolation (if one file is locked or protected, remaining files proceed safely).
  - Safe cancellation support at any time.
- **Full Undo Operation**:
  - SQLite persistent history tracking every rename session and file with SHA-256 hashes and timestamps.
  - Safe reversal engine that verifies the file still exists and the original location is not occupied.
- **Detailed Audit Reports**:
  - **CSV Report**: Excel-compatible (UTF-8 with BOM `utf-8-sig`) with full paths, status, size, SHA-256 hash, and explanations.
  - **TXT Report**: Clean, readable executive summary and file-by-file log.
  - **JSON Report**: Machine-readable audit export for external tools and compliance.
- **100% Local & Privacy-Preserving**:
  - No file contents or telemetry are transmitted over the internet.
  - All processing is conducted locally on your machine.

---

## 📂 Supported File Formats

| Format Category | Supported Extensions | Content Extraction Strategy |
|---|---|---|
| **PDF Documents** | `.pdf` | Metadata (Title, Author, Subject) + Page 1 headings & text via `pypdf`. Encrypted PDF detection. |
| **Word Documents** | `.docx` | Core properties + Title/Heading styles + opening paragraphs via `python-docx`. |
| **Excel Spreadsheets** | `.xlsx` | Workbook title + worksheet names + column headers via `openpyxl`. |
| **PowerPoint** | `.pptx` | Presentation title + slide 1 header and text shapes via `python-pptx`. |
| **Text, Web & Config** | `.txt`, `.md`, `.json`, `.csv`, `.tsv`, `.xml`, `.html`, `.svg`, `.url`, `.tex`, `.yaml`, `.toml`, `.ini` | Markdown `#` headers, YAML frontmatter, HTML `<title>`, SVG `<title>`, URL shortcut domains, LaTeX `\title`, JSON top keys, CSV headers with chunked safe streaming. |
| **Source Code & Shaders** | `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.cs`, `.go`, `.rs`, `.sql`, `.frag`, `.vert`, `.glsl`, `.hlsl`, `.dart` | Module docstrings, leading comments, primary class/interface definitions, shader descriptions, and pipeline stages. |
| **Executables & Installers** | `.exe`, `.dll`, `.sys`, `.msi`, `.vsix` | Windows PE metadata (ProductName, FileDescription, ProductVersion) via `pefile` and VS Code VSIX manifests (DisplayName). |
| **Audio & Media** | `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.mp4`, `.mkv`, `.mov` | WAV RIFF INFO chunks (`INAM`, `IART`), ID3 audio tags (artist, title), and duration calculation. |
| **Fonts** | `.ttf`, `.otf`, `.woff`, `.woff2` | Pure-Python OpenType/TrueType `name` table parsing extracting Font Family and Full Font Name (e.g., `HoneyBear Italic`). |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.tiff` | EXIF metadata (camera, description, date) or **AI Vision (Groq Cloud Qwen 3.8 27B / Google Gemini)** (scenes, logos, documents, screenshots, objects), plus resolution structuring. |
| **Archives** | `.zip`, `.tar`, `.tar.gz`, `.tar.bz2`, `.7z`, `.rar`, `.iso`, `.whl` | Internal package/directory root names without extracting files to disk. |
| **Universal Fallback** | All other formats (`.bin`, `.dat`, `.db`, `.tmp`, `.pak`, etc.) | **100% Supported**: Safe categorization, naming convention cleaning, and data integrity preservation. |

---

## 🚀 Quick Start for Developers

### 1. Prerequisites
- Python 3.10 or higher (Python 3.10, 3.11, 3.12, 3.13, 3.14 supported).

### 2. Installation
```bash
# Clone or navigate to the workspace
cd scripts

# Install required dependencies
pip install -r requirements.txt
```

### 3. Running the Desktop Application
```bash
python main.py
```
*(or `python src/main.py`)*

### 4. Running the Automated Test Suite
```bash
python -m pytest tests/ -v
```

---

## 📦 Building Standalone Executables

No Python installation is required for end users when running packaged executables.

### Windows (.exe)
Run the automated Windows build script:
```cmd
build_scripts\build_windows.bat
```
Output: `dist\SmartFileOrganizer.exe`

### macOS (.app)
Run the macOS build script:
```bash
chmod +x build_scripts/build_macos.sh
./build_scripts/build_macos.sh
```
Output: `dist/SmartFileOrganizer.app`

> 📘 **Detailed macOS Guide**: See [docs/INSTALL_MAC.md](docs/INSTALL_MAC.md) for step-by-step instructions on running from source, building `.app` bundles, creating `.dmg` installers, and handling macOS Gatekeeper permissions.

### Linux (Binary / AppImage)
Run the Linux build script:
```bash
chmod +x build_scripts/build_linux.sh
./build_scripts/build_linux.sh
```
Output: `dist/SmartFileOrganizer`

---

## ⚙️ Configuration & Naming Rules

Click **Settings** (`⚙️`) in the application to customize:
- **Naming Conventions**: `Title_Case`, `snake_case`, `kebab-case`, `CamelCase`, `Sentence_case`.
- **Word Separators**: Underscore (`_`), Hyphen (`-`), or Space (` `).
- **Max Filename Length**: Configurable limit (default: 80 characters, platform max 255).
- **Date Prefix**: Automatically prepend modification dates (`YYYY-MM-DD_...`).
- **Safe Size Limits**: Limit deep inspection on files exceeding a threshold (default: 100 MB).

---

## 🛡️ Limitations & Troubleshooting

- **Encrypted / Password-Protected Files**: Protected files cannot have their text read without the password. The organizer will flag them safely in the preview table and retain the original filename.
- **Scanned Images inside PDFs**: Text extraction on image-only PDFs requires OCR. If OCR is disabled or text is not present, the original name is safely kept with a clear explanation in the table.
- **In-Use / Locked Files**: On Windows, files currently open with exclusive write locks in other applications will report a lock warning; other files continue without interruption.
- **Path Length Restrictions**: Standard Windows path limits (MAX_PATH) are safely guarded with sanitization and character length limits.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
