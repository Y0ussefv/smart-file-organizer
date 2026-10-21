@echo off
setlocal enabledelayedexpansion
title Smart File Organizer - Windows Installer
color 0A

echo ==============================================================================
echo           SMART FILE ORGANIZER - WINDOWS INSTALLER
echo ==============================================================================
echo.

set "SOURCE_EXE=%~dp0dist\SmartFileOrganizer.exe"

if not exist "!SOURCE_EXE!" (
    echo [ERROR] Compiled executable not found at:
    echo "!SOURCE_EXE!"
    echo.
    echo Please make sure the build has finished or build it using build_scripts\build_windows.bat.
    echo.
    pause
    exit /b 1
)

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\SmartFileOrganizer"
set "TARGET_EXE=%INSTALL_DIR%\SmartFileOrganizer.exe"

echo [1/4] Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [2/4] Installing application files to:
echo       %INSTALL_DIR%
copy /Y "!SOURCE_EXE!" "%TARGET_EXE%" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to copy application executable.
    pause
    exit /b 1
)

echo [3/4] Creating Desktop and Start Menu shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$deskPath = [Environment]::GetFolderPath('Desktop'); " ^
    "$scDesktop = $ws.CreateShortcut(\"$deskPath\Smart File Organizer.lnk\"); " ^
    "$scDesktop.TargetPath = '%TARGET_EXE%'; " ^
    "$scDesktop.WorkingDirectory = '%INSTALL_DIR%'; " ^
    "$scDesktop.Description = 'Intelligent Content-Aware File Organizer and Renamer'; " ^
    "$scDesktop.Save(); " ^
    "$smPath = [Environment]::GetFolderPath('Programs'); " ^
    "$scStart = $ws.CreateShortcut(\"$smPath\Smart File Organizer.lnk\"); " ^
    "$scStart.TargetPath = '%TARGET_EXE%'; " ^
    "$scStart.WorkingDirectory = '%INSTALL_DIR%'; " ^
    "$scStart.Description = 'Intelligent Content-Aware File Organizer and Renamer'; " ^
    "$scStart.Save();"

echo [4/4] Creating uninstaller script...
(
    echo @echo off
    echo title Smart File Organizer - Uninstaller
    echo echo Uninstalling Smart File Organizer...
    echo powershell -NoProfile -Command "Remove-Item -Path \"$([Environment]::GetFolderPath('Desktop'))\Smart File Organizer.lnk\" -Force -ErrorAction SilentlyContinue; Remove-Item -Path \"$([Environment]::GetFolderPath('Programs'))\Smart File Organizer.lnk\" -Force -ErrorAction SilentlyContinue"
    echo cd /d "%%TEMP%%"
    echo rd /s /q "%INSTALL_DIR%" 2^>nul
    echo echo Smart File Organizer has been successfully uninstalled.
    echo pause
) > "%INSTALL_DIR%\uninstall.bat"

echo.
echo ==============================================================================
echo [SUCCESS] Smart File Organizer has been successfully installed!
echo.
echo • Desktop Shortcut: Created
echo • Start Menu:       Added to Programs
echo • Location:         %INSTALL_DIR%
echo ==============================================================================
echo.

set /p RUN_NOW="Do you want to launch Smart File Organizer now? (Y/N): "
if /i "!RUN_NOW!"=="Y" (
    start "" "%TARGET_EXE%"
)

exit /b 0
