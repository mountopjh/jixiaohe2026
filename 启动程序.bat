@echo off
echo 初始化路径...
cd /d "%~dp0"

echo 设置浏览器本地读取标志...
set PLAYWRIGHT_BROWSERS_PATH=0

echo 正在启动程序，请稍候...
venv\Scripts\python main.py

pause
