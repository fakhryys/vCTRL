@echo off
echo Building vCTRL executable...
echo.

REM Install PyInstaller if not already installed
pip install pyinstaller >nul 2>&1

REM Build the executable
pyinstaller --onefile --windowed --name vCTRL --icon=NONE ^
    --add-data "config.json;." ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    mouse_to_joystick.py

echo.
echo Build complete!
echo Executable location: dist\vCTRL.exe
echo.
pause
