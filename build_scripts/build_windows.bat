@echo off
REM ==============================================================================
REM Build Standalone Windows Executable for Smart File Organizer
REM ==============================================================================

echo [1/3] Checking Python and dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [2/3] Running automated tests...
python -m pytest tests/
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Automated tests failed! Aborting build.
    exit /b %ERRORLEVEL%
)

echo [3/3] Compiling standalone Windows executable with PyInstaller...
python -m PyInstaller --clean --noconfirm smart_file_organizer.spec

if exist "dist\SmartFileOrganizer.exe" (
    echo ==============================================================================
    echo [SUCCESS] Standalone Windows executable built successfully!
    echo Location: dist\SmartFileOrganizer.exe
    echo ==============================================================================
) else (
    echo [ERROR] Build failed. Output executable not found.
    exit /b 1
)
