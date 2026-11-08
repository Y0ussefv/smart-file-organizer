@echo off
REM BeeOrganizer - runs the Windows installer built by build_scripts\build_windows.bat
if exist "%~dp0dist\BeeOrganizer-Setup.exe" (
    start "" "%~dp0dist\BeeOrganizer-Setup.exe"
) else (
    echo dist\BeeOrganizer-Setup.exe not found. Build it first: build_scripts\build_windows.bat
    pause
)
