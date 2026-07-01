@echo off
title OEM Lookup Tool — Full Setup
setlocal

echo.
echo ============================================
echo  OEM Price Lookup — Full Setup
echo ============================================
echo.

:: ── Step 1: Check / Install Python ───────────────────────────────────────────
echo [1/4] Checking for Python...
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo       Python found. OK
    goto :install_packages
)

echo       Python not found. Downloading Python 3.12 installer...
echo       (This may take 1-2 minutes depending on your connection)
echo.

powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%TEMP%\python_installer.exe' -UseBasicParsing" >nul 2>&1

if not exist "%TEMP%\python_installer.exe" (
    echo.
    echo ERROR: Could not download Python automatically.
    echo.
    echo Please install it manually:
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Click "Download Python 3.x.x"
    echo   3. Run the installer
    echo   4. IMPORTANT: Check "Add Python to PATH" at the bottom of the installer
    echo   5. Click Install Now
    echo   6. Re-run this setup after installing.
    echo.
    pause & exit /b 1
)

echo       Installing Python silently (with PATH)...
"%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
del "%TEMP%\python_installer.exe" >nul 2>&1

echo       Python installed. Reopening setup with updated PATH...
echo.

:: Re-launch this script in a NEW cmd so PATH is refreshed
cmd /c ""%~f0""
exit /b

:: ── Step 2: Install Python packages ──────────────────────────────────────────
:install_packages
echo.
echo [2/4] Installing Python packages (playwright, openpyxl, pywin32)...
python -m pip install playwright openpyxl pywin32 playwright-stealth --quiet --upgrade
if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause & exit /b 1
)
echo       Packages installed. OK

:: ── Step 3: Install Chromium browser ─────────────────────────────────────────
echo.
echo [3/4] Installing Chromium browser for web automation...
python -m playwright install chromium
if errorlevel 1 (
    echo ERROR: Playwright Chromium install failed.
    pause & exit /b 1
)
echo       Chromium installed. OK

:: ── Step 4: Add button to Excel ───────────────────────────────────────────────
echo.
echo [4/4] Adding the "Buscar Precios OEM" button to Excel...
echo       Make sure cotizacion_bulk.xlsm is CLOSED right now.
echo.
python "%~dp0add_excel_button.py"
if errorlevel 1 (
    echo.
    echo NOTE: Button could not be added automatically.
    echo You can still run prices from the command line:
    echo   python oem_lookup.py
    echo.
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  Open cotizacion_bulk.xlsm and click the
echo  [Buscar Precios OEM] button to look up prices.
echo ============================================
echo.
pause
