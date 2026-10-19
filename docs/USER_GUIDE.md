# Smart File Organizer & Intelligent File Renamer — User Guide

Welcome to **Smart File Organizer**, a desktop application designed to organize and rename your digital documents, spreadsheets, slides, code, and images based on their actual content and metadata.

---

## 1. Getting Started

### Launching the Application
- **From Source**:
  ```bash
  python main.py
  ```
- **From Standalone Executable**:
  Double-click `SmartFileOrganizer.exe` (Windows) or `SmartFileOrganizer.app` (macOS).

---

## 2. Interface Overview

The application features a clean, responsive graphical interface:

### 1. Dashboard (Top Area)
- **Select Folder**: Click `📁 Select Folder...` to choose any directory on your computer using the native folder picker.
- **Include Subfolders**: Check this box if you wish to recursively scan all subfolders inside the chosen directory.
- **Theme Switcher**: Click `☀️ Light Mode` / `🌙 Dark Mode` in the upper-right corner to toggle between themes.
- **Action Buttons**:
  - `🔍 Start Scan`: Scans the chosen directory and extracts descriptive titles.
  - `👁️ Refresh Preview`: Re-analyzes current files with updated naming rules.
  - `✓ Rename Files`: Safely renames all checked files after showing a confirmation dialog.
  - `⏹ Cancel`: Stops any running scan or rename task cleanly.
  - `📊 Export Reports`: Generates CSV, TXT, and JSON audit reports in any directory.

### 2. Summary KPI Cards
Live indicator cards display:
- **Total Scanned**: Total number of files discovered.
- **Supported**: 100% of all files encountered (every document, media, executable, font, code, or data file).
- **Unsupported**: 0 (all files on the system are safely recognized and supported).
- **Ready to Rename**: Files where a meaningful, descriptive title was established or structured cleaning applies.
- **Unchanged / Safe**: Files that already match their ideal name, or are safely preserved.
- **Errors**: Files with permission locks or corrupt structures.

### 3. File Preview Table
Before any file is modified on disk, all proposals are presented in an interactive preview table:
- **Checkbox (Column 1)**: Include or exclude individual files from renaming.
- **Original Filename**: The current filename on disk.
- **Proposed New Filename**: The proposed content-based filename. **You can double-click this cell to edit it manually!**
- **Ext**: File extension (including compound extensions like `.tar.gz`).
- **File Type**: Categorized type (e.g. PDF Document, Word Document, Excel Spreadsheet).
- **Size**: Formatted file size (e.g. `2.4 MB`).
- **Detected Title / Summary**: The extracted heading or metadata.
- **Status Badge**: Visual status pill (Ready, Renamed, Unchanged, Skipped, Error).
- **Explanation**: Detailed reason describing how the title was derived.

### 4. Search and Filtering
Above the table, use the filter bar to:
- **Search**: Type any keyword to filter across filenames, extensions, titles, and explanations.
- **Status Filter**: View only "Ready to Rename", "Errors", or "Unchanged" items.
- **Type Filter**: Filter by specific formats (e.g. PDF, Word, Excel, Images).
- **Select All / Deselect All**: Quick mass-selection toggles.

---

## 3. Renaming Workflow

1. **Select a Directory**: Click `📁 Select Folder...` and choose the folder you want to organize.
2. **Review Proposals**: Examine the proposed names in the Preview Table.
   - If you want to modify a proposed name, double-click the cell in the `Proposed New Filename` column, enter your preferred name, and hit Enter.
   - If you don't want a particular file renamed, simply uncheck its checkbox.
3. **Click `✓ Rename Files`**:
   - A confirmation dialog appears summarizing the files that will be modified.
   - Click `Rename Now` to execute.
4. **Automatic Safety**:
   - Files are renamed atomically.
   - If a target filename already exists, a deterministic suffix (`_2`, `_3`, etc.) is added so no file is ever overwritten.
   - After renaming, the application automatically verifies that the new file exists on disk and its size matches the original.

---

## 4. Undoing File Renames

If you ever need to revert a rename operation:
1. Click the `↺ Undo Session` button in the top navigation bar.
2. Select the session you want to reverse from the list of previous sessions.
3. Review the files that will be restored.
4. Click `Revert Selected Session`.
5. The application restores every file to its exact original filename after verifying that the destination path is unoccupied.

> [!NOTE]
> Filename changes are reversible through history only when the relevant files remain in the folder and no conflicting changes prevent reversal.

---

## 5. Exporting Audit Reports

After every operation, the application automatically creates reports in your application data directory. You can also export reports manually at any time by clicking `📊 Export Reports`.

### Available Report Formats:
- **CSV Report**: Excel-compatible UTF-8 with BOM (`utf-8-sig`) containing timestamp, original and new paths, file sizes, SHA-256 hashes, status, and explanations.
- **TXT Report**: Clean human-readable summary detailing scan statistics and individual file audit entries.
- **JSON Report**: Structured machine-readable report containing the entire session audit record.

---

## 6. Configuring Naming Rules

Click `⚙️ Settings` to customize naming behavior:
- **Naming Style Convention**:
  - `Title_Case`: e.g., `CI_CD_Deployment_Guide.pdf`
  - `snake_case`: e.g., `ci_cd_deployment_guide.pdf`
  - `kebab-case`: e.g., `ci-cd-deployment-guide.pdf`
  - `CamelCase`: e.g., `CiCdDeploymentGuide.pdf`
  - `Sentence_case`: e.g., `Ci_cd_deployment_guide.pdf`
- **Space Replacement Separator**: Choose between underscore (`_`), hyphen (`-`), or space (` `).
- **Maximum Filename Length**: Set maximum characters (default: 80, maximum 255).
- **Date Prefix**: Automatically prefix the file modification date (e.g. `2026-10-19_...`).
- **Safe Size Limits**: Limit deep content extraction on files over a certain size (default: 100 MB).
- **Google AI Image Recognition (Gemini Vision)**:
  - Check **Enable Google AI Image Recognition**.
  - Enter your **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/)).
  - Click **⚡ Test API Key** to verify your connection.
  - Choose your preferred model (`gemini-1.5-flash`, `gemini-2.0-flash`, or `gemini-1.5-pro`).
  - When enabled, image files (e.g., `4a73b82d...png`) will be analyzed visually and renamed to concise descriptive titles matching the actual scene or subject (e.g., `Eiffel_Tower_Sunset.png`, `Company_Revenue_Chart.png`). All documents and other files remain 100% local.

---

## 7. Universal File Format Support

Smart File Organizer supports **100% of files on your computer** without leaving any format unsupported:

| Category | Extensions | Extraction & Renaming Logic |
| :--- | :--- | :--- |
| **Documents** | `.pdf`, `.docx`, `.xlsx`, `.pptx` | Extracts document titles, metadata properties, headings, sheet names, table headers. |
| **Text & Data** | `.txt`, `.md`, `.json`, `.csv`, `.tsv`, `.xml`, `.html`, `.svg`, `.url`, `.tex`, `.latex`, `.toml`, `.yaml`, `.ini`, `.cfg` | Extracts frontmatter, H1 tags, JSON keys, CSV column headers, SVG titles, internet shortcut domains, LaTeX titles, config names. |
| **Source Code & Shaders** | `.py`, `.js`, `.ts`, `.cpp`, `.cs`, `.go`, `.rs`, `.frag`, `.vert`, `.glsl`, `.hlsl`, `.dart`, etc. | Extracts module docstrings, main class definitions, shader descriptions, and pipeline stages. |
| **Executables & Installers** | `.exe`, `.dll`, `.sys`, `.msi`, `.vsix` | Inspects PE headers (ProductName, FileDescription, ProductVersion) and VSIX package manifests (DisplayName). |
| **Audio & Video** | `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.mp4`, `.mkv`, `.mov` | Extracts artist, track title from ID3 tags and WAV RIFF INFO chunks; formats media duration and type. |
| **Fonts** | `.ttf`, `.otf`, `.woff`, `.woff2` | Parses OpenType/TrueType `name` tables to extract Font Family and Full Font Name (e.g., `HoneyBear Italic`). |
| **Archives** | `.zip`, `.tar`, `.gz`, `.bz2`, `.xz`, `.7z`, `.rar`, `.iso`, `.whl` | Inspects root package names, README entries, or top-level project structures. |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` | EXIF camera/timestamp metadata, Google Gemini Vision visual recognition, and resolution structuring. |
| **System & Binary Fallback** | `.bin`, `.dat`, `.db`, `.sqlite`, `.tmp`, `.pak`, `.rom`, `.apk`, `.dmg`, etc. | 100% supported! Categorizes file types, enforces naming convention sanitization, and preserves data safety. |

