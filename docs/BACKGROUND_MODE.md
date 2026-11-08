# BeeOrganizer background mode – rename every new download, from any app

`BeeOrganizer.exe` (Windows) / `BeeOrganizer.app` (macOS) now runs in the
background with an icon near the clock (Windows) or in the menu bar (macOS).
It watches your **Downloads** folder and renames every new file as soon as it has finished
downloading, whichever app downloaded it (Chrome, Edge, Firefox, Safari, WhatsApp, Teams, Outlook…).

```
New file appears in Downloads  →  wait until it stops growing  →  read content (+ OpenAI if a key is set)
                               →  "26-11 Bee_Diagnostic_Et_Cadrage.pdf"  →  notification (+ Undo in the menu)
```

- Files already in Downloads when the app starts are **never** touched.
- Unfinished downloads (`.crdownload`, `.part`, `.tmp`…) are ignored until they're complete.
- Files that already start with `YY-MM ` (for example renamed by the BeeOrganizer Chrome extension) are skipped, so nothing is renamed twice.
- Nothing is ever overwritten: if the name exists, `_2` is added. Every rename can be undone.

## Windows

**For users:** download `BeeOrganizer-Setup.exe` from
https://github.com/Y0ussefv/smart-file-organizer/releases/latest and run it. No admin rights are needed. The installer:
- installs to `%LOCALAPPDATA%\Programs\BeeOrganizer`;
- adds Start menu and Desktop shortcuts;
- starts BeeOrganizer with Windows (it shows in **Task Manager → Startup apps** as *BeeOrganizer · RNJ*);
- lists it in **Settings → Apps → Installed apps**, with **Uninstall**.

Then: right-click the bee icon → **Open BeeOrganizer** → **Settings → OpenAI Precise Titles** → paste the key → **Save**.

If Windows says "Windows protected your PC" (the app isn't code-signed yet, see [SIGNING.md](SIGNING.md)): **More info → Run anyway**.

**For developers:** `build_scripts\build_windows.bat` builds `dist\BeeOrganizer.exe` and `dist\BeeOrganizer-Setup.exe` (needs Inno Setup: `winget install JRSoftware.InnoSetup`).

## macOS

Download `BeeOrganizer-mac-AppleSilicon.dmg` (M1/M2/M3/M4 Macs) or `BeeOrganizer-mac-Intel.dmg` from the same releases page. GitHub builds them automatically; to build yourself on a Mac, run `bash build_scripts/build_macos.sh`.

1. Open the `.dmg` and drag **BeeOrganizer** onto **Applications**.
2. First launch: **right-click → Open → Open** (the app isn't signed by Apple).
3. Allow access to the **Downloads** folder when macOS asks.
4. Answer **Yes** to "Start automatically…". This creates `~/Library/LaunchAgents/com.rnj.beeorganizer.plist`.
5. Add the OpenAI key in Settings, as on Windows.

## Smart project folders (like a human organizer)

On by default (menu: **Smart project folders**). It needs an OpenAI key for the "thinking" part.

**A folder arrives in Downloads** (an unzipped archive, a copied folder…). BeeOrganizer waits until it stops changing, then:
1. **Removes useless nesting**: `folderX/folderY/FILES` → `folderX/FILES`.
2. **Leaves software projects alone**: if the folder contains `.git`, `package.json`, `pyproject.toml`, `.sln`…, it's only unwrapped and never rearranged.
3. **Builds a project folder** from the files' real content, with subfolders **only when useful** (more than 5 files and at least 2 per category):
   ```
   26-11 Project Delfa/
   ├── Contact/   26-11 Delfa_Contact_Ahmed.vcf, …
   ├── Assets/    26-11 Delfa_Logo.png, …
   └── 26-11 Contrat_Delfa_2026.pdf
   ```
4. **Merges into an existing project** when the content belongs there (new Delfa files go into your existing `Project Delfa`).

**A single file arrives**: it's renamed, then filed into the matching existing project folder (e.g. `Project Delfa/Assets`) only when it clearly belongs there. Otherwise it stays in Downloads.

**Organize Downloads now…** (menu): plans a clean-up of the whole Downloads folder. It unwraps nested folders and groups loose files into projects (a new folder only when at least 2 files share a project). It first **shows the plan** (Show Details lists every move) and does nothing until you click **Yes**.

Everything can be undone with **Undo last rename**. Nothing is ever overwritten. Only empty folders and system junk (`.DS_Store`, `Thumbs.db`, `__MACOSX`) are deleted.

## Tray / menu-bar menu

| Item | What it does |
|---|---|
| Pause renaming | Stops renaming until you untick it |
| Recent renames | Last 10 renames. Click one to show it in Explorer / Finder |
| Undo last rename | Puts back the last file or folder exactly as it was |
| Organize Downloads now… | Previews, then applies a clean-up of the whole Downloads folder |
| Smart project folders | Project folders and subfolders chosen from the content (on by default) |
| Open Downloads folder | |
| Add date prefix (26-11 …) | On by default |
| Sort into type folders | `Documents/`, `Images/`, `Archives/`… inside Downloads |
| Start when the computer starts | Turns automatic start on or off |
| Open BeeOrganizer | Main window (settings, OpenAI key, manual folder scan) |
| Quit BeeOrganizer | Stops watching until the next start-up (or a double-click on the app) |

## Command line

```
BeeOrganizer.exe              window + background watcher
BeeOrganizer.exe --watch      background only (used at start-up)
BeeOrganizer.exe --no-watch   window only (old behaviour)
```

From source: `python main.py`, `python main.py --watch`, `python main.py --no-watch`.

Logs: `%APPDATA%\SmartFileOrganizer\logs\smart_file_organizer.log` (macOS: `~/Library/Application Support/SmartFileOrganizer/logs/`).
