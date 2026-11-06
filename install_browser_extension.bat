@echo off
REM Connects the Smart File Organizer browser extension to this app (Chrome, Edge, Brave).
cd /d "%~dp0"
python main.py --install-browser-bridge
if errorlevel 1 (
  echo.
  echo Install failed. Make sure Python is installed and requirements are installed:
  echo     pip install -r requirements.txt
)
echo.
echo Now open chrome://extensions , turn on Developer mode, click "Load unpacked"
echo and choose the folder:  %~dp0browser_extension
echo.
pause
