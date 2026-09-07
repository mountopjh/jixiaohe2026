@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

echo ==========================================
echo Build versioned one-file EXE
echo ==========================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  exit /b 1
)

set "VENV_DIR=.build_venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "RELEASE_DIR=%cd%\BankBin_Releases"

if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
if errorlevel 1 (
  echo [ERROR] Failed to create release directory: %RELEASE_DIR%
  exit /b 1
)

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

if exist ".\build" rmdir /s /q ".\build"

set "BUILD_SEQ="
for /f %%N in ('%PY% -c "import os,re,sys; nums=[int(m.group(1)) for name in os.listdir(sys.argv[1]) if (m:=re.fullmatch(r'BankBin_(\d+)\.exe', name, re.I))]; print(f'{max(nums, default=0) + 1:03d}')" "%RELEASE_DIR%"') do set "BUILD_SEQ=%%N"
if not defined BUILD_SEQ (
  echo [ERROR] Failed to determine the next build sequence.
  exit /b 1
)

set "BUILD_NAME=BankBin_!BUILD_SEQ!"
set "BANKBIN_BUILD_NAME=!BUILD_NAME!"

echo [INFO] Building !BUILD_NAME!.exe...
"%PY%" -m PyInstaller ^
  --clean ^
  --noconfirm ^
  --distpath "%RELEASE_DIR%" ^
  --workpath ".\build" ^
  ".\BankBin.spec"

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

if exist "%RELEASE_DIR%\!BUILD_NAME!.exe" (
  echo [OK] Build done: %RELEASE_DIR%\!BUILD_NAME!.exe
) else (
  echo [ERROR] Build failed.
  exit /b 1
)

endlocal
