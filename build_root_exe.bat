@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

echo ==========================================
echo Build one-file EXE to project root
echo ==========================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  exit /b 1
)

set "VENV_DIR=.build_venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" goto :create_env

"%PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [WARN] Existing venv has no pip, recreating...
  if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
  goto :create_env
)
goto :env_ready

:create_env
echo [INFO] Creating build venv: %VENV_DIR%
python -m venv "%VENV_DIR%"
if errorlevel 1 (
  echo [WARN] python -m venv failed, trying virtualenv fallback...
  python -m pip install virtualenv
  if errorlevel 1 (
    echo [ERROR] Failed to install virtualenv.
    exit /b 1
  )
  python -m virtualenv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERROR] Failed to create build venv via virtualenv.
    exit /b 1
  )
)

set "PY=%VENV_DIR%\Scripts\python.exe"
"%PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] Bootstrapping pip with ensurepip...
  "%PY%" -m ensurepip --upgrade
)

"%PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] pip is still unavailable in %VENV_DIR%.
  exit /b 1
)

:env_ready
echo [INFO] Upgrading pip...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip.
  exit /b 1
)

echo [INFO] Installing project dependencies...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  exit /b 1
)

echo [INFO] Installing PyInstaller...
"%PY%" -m pip install pyinstaller
if errorlevel 1 (
  echo [ERROR] Failed to install PyInstaller.
  exit /b 1
)

echo [INFO] Verifying critical imports...
"%PY%" -c "import PyQt6, keyboard, pyperclip, playwright, requests, pynput, pandas, openpyxl"
if errorlevel 1 (
  echo [ERROR] Dependency import check failed.
  exit /b 1
)

if exist ".\Jixiaohe.exe" del /f /q ".\Jixiaohe.exe"
if exist ".\build" rmdir /s /q ".\build"

set "MD_ADD_DATA="
for %%F in (*.md) do (
  if exist "%%~fF" (
    set "MD_ADD_DATA=!MD_ADD_DATA! --add-data=%%~nxF:."
  )
)

echo [INFO] MD add-data args: !MD_ADD_DATA!

echo [INFO] Building EXE...
"%PY%" -m PyInstaller ^
  --clean ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "Jixiaohe" ^
  --add-data=bin_database.db:. ^
  !MD_ADD_DATA! ^
  --distpath "." ^
  --workpath ".\build" ^
  --specpath "." ^
  ".\main.py"

if exist ".\Jixiaohe.exe" (
  echo [OK] Build done: %cd%\Jixiaohe.exe
) else (
  echo [ERROR] Build failed.
  exit /b 1
)

endlocal
