@echo off
chcp 65001 >nul
echo =============================================
echo  纪小盒 - 一键打包 EXE 工具
echo =============================================
echo.

:: 切换到脚本目录
cd /d "%~dp0"

:: 激活虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 找不到虚拟环境，请先运行"一键安装环境并配置.bat"
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

:: 安装 PyInstaller（如果没有）
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装 PyInstaller...
    pip install pyinstaller
)

echo.
echo [提示] 正在打包，请稍候...
echo.

:: 打包主程序为单文件 exe，带窗口不弹黑框
pyinstaller --noconfirm --onefile --windowed ^
  --name "纪小盒" ^
  main.py

echo.
if exist "dist\纪小盒.exe" (
    echo [成功] 打包完成！文件位置:
    echo   dist\纪小盒.exe
) else (
    echo [警告] 未找到输出文件，请检查上方错误信息
)

echo.
pause
