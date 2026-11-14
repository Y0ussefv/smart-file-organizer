# BeeOrganizer background mode – rename every new download, from any app

`BeeOrganizer.exe` (Windows) / `BeeOrganizer.app` (macOS) now runs in the
background with an icon near the clock (Windows) or in the menu bar (macOS).
It watches your **Downloads** folder and renames every new file as soon as it has finished
downloading, whichever app downloaded it (Chrome, Edge, Firefox, Safari, WhatsApp, Teams, Outlook…).

```
New file appears in Downloads  →  wait until it stops growing  →  read content (on this computer)
                               →  "26-11 Bee_Diagnostic_Et_Cadrage.pdf"  →  notification (+ Undo in the menu)
```

- Files already in Downloads when the app starts are **never** touched.
- Unfinished downloads (`.crdownload`, `.part`, `.tmp`…) are ignored until they're complete.
- Files that already start with `YY-MM ` are skipped, so nothing is renamed twice.
- Nothing is ever overwritten: if the name exists, `_2` is added. Every rename can be undone.

## Windows

**For users:** download `BeeOrganizer-Setup.exe` from
https://github.com/Y0ussefv/smart-file-organizer/releases/latest and run it. No admin rights are needed. The installer:
- installs to `%LOCALAPPDATA%\Programs\BeeOrganizer`;
- adds Start menu and Desktop shortcuts;
- starts BeeOrganizer with Windows (it shows in **Task Manager → Startup apps** as *BeeOrganizer · RNJ*);
- lists it in **Settings → Apps → Installed apps**, with **Uninstall**.

If Windows says "Windows protected your PC" (the app isn't code-signed yet, see [SIGNING.md](SIGNING.md)): **More info → Run anyway**.

**For developers:** `build_scripts\build_windows.bat` builds `dist\BeeOrganizer.exe` and `dist\BeeOrganizer-Setup.exe` (needs Inno Setup: `winget install JRSoftware.InnoSetup`).

## macOS

Download `BeeOrganizer-mac-AppleSilicon.dmg` (M1/M2/M3/M4 Macs) or `BeeOrganizer-mac-Intel.dmg` from the same releases page. GitHub builds them automatically; to build yourself on a Mac, run `bash build_scripts/build_macos.sh`.

1. Open the `.dmg` and drag **BeeOrganizer** onto **Applications**.
2. First launch: **right-click → Open → Open** (the app isn't signed by Apple).
3. Allow access to the **Downloads** folder when macOS asks.
4. Answer **Yes** to "Start automatically…". This creates `~/Library/LaunchAgents/com.rnj.beeorganizer.plist`.

## How a download is handled (2.0)

1. **Local check.** BeeOrganizer reads the file on the computer and classifies it: **P0** public, **P1**
   confidential / personal, **P2** very sensitive, **INCONNU** unreadable. See [PRIVACY.md](PRIVACY.md).
2. **Exact name** `YY-MM Title.ext`, from the content. Nothing invented: without a reliable title the
   original name is kept. Never overwrites (`_2`, `_3`…).
3. **Filing, only into approved projects** (🐝 → **Projects…**), compared with **all** of them, never "the
   last folder":
   * strong and specific evidence (the project name **and** one of its references, no contradiction, clear
     lead over any other project) → moved to `Downloads/Projets/<Project>/` (or an approved category);
   * possible match → stays in Downloads, with a **proposal** (🐝 → **Proposals…**);
   * no match → stays in Downloads, renamed.
4. **New project?** When 3 different files clearly name the same unknown project (e.g. "Projet Delfa"),
   BeeOrganizer **proposes** it, with the list of files and the target folder. Nothing is created before
   you accept. Refused proposals leave everything as it is.
5. **Undo** puts back the name **and** the place, and removes folders the app created if they are empty.

Folders you receive (unzipped archives, copied folders, software projects) are **left as they are**.
At most two levels are ever created: `Projets/<Project>/<Category>/file`.

## Cloud analysis (optional, off by default)

🐝 → **Privacy and cloud analysis…** explains what may be sent and lets you turn it on. Only a short,
redacted excerpt of **P0 (public)** documents can be sent to OpenAI to get a more precise name. P1, P2 and
INCONNU documents, and every file of a project marked **always local**, never leave the computer.

## Tray / menu-bar menu

| Item | What it does |
|---|---|
| Pause renaming | Stops renaming until you untick it |
| Recent renames | Last 10 renames. Click one to show it in Explorer / Finder |
| Undo last rename | Puts back the last file exactly as it was (name and place) |
| Proposals… | Suggested filings and new projects: Accept, Choose another project, Leave in Downloads |
| Projects… | Approved projects: name, aliases, references, exclusions, always local, categories |
| Privacy and cloud analysis… | Cloud switch (off by default), OpenAI key (system vault), purge history |
| Open Downloads folder | |
| Add date prefix (26-11 …) | On by default |
| Start when the computer starts | Turns automatic start on or off |
| Open BeeOrganizer | Main window (settings, manual folder scan with preview) |
| Quit BeeOrganizer | Stops watching until the next start-up (or a double-click on the app) |

## Command line

```
BeeOrganizer.exe              window + background watcher
BeeOrganizer.exe --watch      background only (used at start-up)
BeeOrganizer.exe --no-watch   window only (old behaviour)
```

From source: `python main.py`, `python main.py --watch`, `python main.py --no-watch`.

Logs: `%APPDATA%\SmartFileOrganizer\logs\smart_file_organizer.log` (macOS: `~/Library/Application Support/SmartFileOrganizer/logs/`).
