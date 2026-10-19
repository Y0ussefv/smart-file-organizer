# macOS Installation & Setup Guide — Smart File Organizer

This guide explains how to install and run **Smart File Organizer & Intelligent File Renamer** on **macOS** (Apple Silicon M1/M2/M3/M4 & Intel).

---

## ⚡ Fast Mini Install (Step-by-Step)

Open your Mac **Terminal** and run:

```bash
# Step 1: Go to project folder
cd /path/to/smart-file-organizer

# Step 2: Create & activate virtual environment
python3 -m venv venv && source venv/bin/activate

# Step 3: Install dependencies
pip install -r requirements.txt

# Step 4: Run the app!
python3 main.py
```

*(If you don't have Python 3 yet: run `brew install python`)*

---

## Option 1: Run from Source (Recommended for Developers)

### 1. Prerequisites
Ensure you have **Python 3.10+** installed. If you don't have it, install it via [Homebrew](https://brew.sh/):
```bash
brew install python
```
Verify the installation:
```bash
python3 --version
```

### 2. Clone / Open the Project Folder
Open Terminal (`Terminal.app` or iTerm2) and navigate to the project directory:
```bash
cd /path/to/smart-file-organizer
```

### 3. Create and Activate a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Launch the Application
```bash
python3 main.py
```

---

## Option 2: Build a Standalone macOS App Bundle (`.app`)

You can generate a standalone `.app` bundle so users do not need Python installed.

### 1. Run the Build Script
Ensure you have your virtual environment activated, then run:
```bash
chmod +x build_scripts/build_macos.sh
./build_scripts/build_macos.sh
```

*(Alternatively, run PyInstaller directly:)*
```bash
pyinstaller --clean --noconfirm --windowed smart_file_organizer.spec
```

### 2. Install to Applications
The build output will be located in the `dist/` directory:
```bash
cp -R dist/SmartFileOrganizer.app /Applications/
```
You can now find **Smart File Organizer** in your **Applications** folder and Launchpad!

---

## 🔒 Important: Handling macOS Gatekeeper Security Notice

Because the app is built locally without an Apple Developer ID signature, macOS Gatekeeper may show a security prompt when opening it for the first time:

> *"SmartFileOrganizer.app cannot be opened because the developer cannot be verified."*

### How to allow and launch the app:

#### Method A: Right-Click (Easiest)
1. In **Finder**, open the **Applications** folder (or navigate to `dist/`).
2. **Right-click** (or `Control + click`) on `SmartFileOrganizer.app` and select **Open**.
3. In the popup dialog, click **Open**. macOS will remember this decision permanently.

#### Method B: System Settings
1. Open **System Settings** ➔ **Privacy & Security**.
2. Scroll down to the **Security** section.
3. Click **Open Anyway** next to the notification for `SmartFileOrganizer.app`.

#### Method C: Terminal (Quarantine Removal)
You can remove the Gatekeeper quarantine flag in one command:
```bash
xattr -cr /Applications/SmartFileOrganizer.app
```

---

## 💽 Optional: Creating a Distribution `.dmg` Installer

To distribute the app to other Mac users as a standard disk image (`.dmg`), run:

```bash
hdiutil create -volname "SmartFileOrganizer" \
  -srcfolder dist/SmartFileOrganizer.app \
  -ov -format UDZO SmartFileOrganizer.dmg
```
This produces `SmartFileOrganizer.dmg`, which users can double-click to drag the app into `/Applications`.

---

## 📂 macOS Permissions (Folder Access)

macOS protects certain user directories (such as `Desktop`, `Documents`, `Downloads`, and removable drives). When you first scan a folder in one of these locations, macOS will ask:

> *"SmartFileOrganizer would like to access files in your Documents folder."*

Click **OK** / **Allow**. If you ever need to change folder permissions:
- Go to **System Settings** ➔ **Privacy & Security** ➔ **Files and Folders** (or **Full Disk Access**).
- Ensure **SmartFileOrganizer** is toggled ON.

---

## ⚙️ Summary of Useful Commands

| Task | Command |
|---|---|
| **Run App** | `python3 main.py` |
| **Run Tests** | `python3 -m pytest tests/` |
| **Build macOS App** | `./build_scripts/build_macos.sh` |
| **Remove Quarantine** | `xattr -cr dist/SmartFileOrganizer.app` |
| **Create .dmg** | `hdiutil create -volname "SmartFileOrganizer" -srcfolder dist/SmartFileOrganizer.app -ov -format UDZO SmartFileOrganizer.dmg` |
