# Making BeeOrganizer look "safe" (code signing)

Unsigned apps trigger warnings:
- **Windows**: "Windows protected your PC" / "Unknown publisher" (SmartScreen).
- **macOS**: "BeeOrganizer cannot be opened because the developer cannot be verified."

## Windows – free signing with SignPath Foundation

SignPath Foundation signs open-source projects for free. This repo qualifies: it's public and MIT-licensed.
The build pipeline (`.github/workflows/release.yml`) is **already prepared**: once the settings below exist,
every release is signed automatically. Only builds made by GitHub Actions can be signed, not local builds.

1. Apply at https://signpath.org/apply with the repository URL `https://github.com/Y0ussefv/smart-file-organizer`.
   Describe the project: "BeeOrganizer – desktop app that gives downloaded files exact names. Built with PyInstaller + Inno Setup on GitHub Actions."
2. After approval, SignPath gives you an **organization ID**, a **project slug** and a **signing policy slug**
   (use the `release-signing` policy). In the SignPath project, add an *artifact configuration* that signs
   the `.exe` inside the uploaded zip (SignPath's default "single PE file in a zip" configuration).
3. Install the SignPath GitHub App on the repository (SignPath shows the link) and create an API token for the CI user.
4. In GitHub: **Settings → Secrets and variables → Actions**
   - New **secret**: `SIGNPATH_API_TOKEN` = the token
   - New **variables**: `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_POLICY_SLUG`
5. Publish a new release (for example `v1.3.1`). The workflow signs `BeeOrganizer.exe` and `BeeOrganizer-Setup.exe`.

Notes:
- With SignPath Foundation, the publisher shown by Windows is **"SignPath Foundation"**, not "RNJ".
  A certificate in your own name means buying one (Certum, Sectigo… or Azure Trusted Signing).
- SmartScreen also builds *reputation*: even signed files may warn for the first downloads, and this fades as more people install it.
- If an antivirus flags the file (it happens with PyInstaller apps), report it as a false positive:
  Microsoft: https://www.microsoft.com/wdsi/filesubmission

## macOS – Apple notarization (optional, 99 USD/year)

Requires the Apple Developer Program. Until then, Mac users open the app the first time with
**right-click → Open → Open** (once). To add it later: a "Developer ID Application" certificate,
then `codesign --deep --options runtime` + `xcrun notarytool submit --wait` + `xcrun stapler staple`
in the macOS job of the workflow.
