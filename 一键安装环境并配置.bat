@echo off
echo 初始化路径并创建虚拟环境...
cd /d "%~dp0"
python -m venv venv

echo 安装 Python 依赖包 (下载到本地文件夹)...
venv\Scripts\pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

echo 强制设定 Playwright 下载到虚拟环境内部目录...
set PLAYWRIGHT_BROWSERS_PATH=0

echo 安装 Playwright 对应的核心浏览器...
venv\Scripts\playwright install chromium

echo.
echo 环境部署完成！请双击 [启动程序.bat] 运行软件。
pause
