@echo off
REM ==============================================================================
REM Build Standalone Windows Executable for Smart File Organizer
REM ==============================================================================

echo [1/4] Checking Python and dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [2/4] Running automated tests...
python -m pytest tests/
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Automated tests failed! Aborting build.
    exit /b %ERRORLEVEL%
)

echo [3/4] Compiling standalone Windows executable with PyInstaller...
python -m PyInstaller --clean --noconfirm smart_file_organizer.spec

if not exist "dist\BeeOrganizer.exe" (
    echo [ERROR] Build failed. Output executable not found.
    exit /b 1
)

echo [4/4] Building the installer (Inno Setup)...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    "%ISCC%" /Q installer\BeeOrganizer.iss
) else (
    echo [WARN] Inno Setup not found - skipping installer. Install it with: winget install JRSoftware.InnoSetup
)

echo ==============================================================================
echo [SUCCESS] dist\BeeOrganizer.exe
if exist "dist\BeeOrganizer-Setup.exe" echo [SUCCESS] dist\BeeOrganizer-Setup.exe  (share this one)
echo ==============================================================================
