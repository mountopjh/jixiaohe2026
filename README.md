# BankBin - 银行BIN码查询

GitHub 项目主页：[mountopjh/BankBin](https://github.com/mountopjh/BankBin)

这是一款专用于查询银行卡 BIN 码及其归属机构的跨平台本地化工具。支持以下核心功能：
- 桌面悬浮窗快捷键查询（选中卡号一键弹出结果）
- 历史查询数据大盘面板
- 本地登录入口（不连接后台、不校验账号密码）
- GitHub 自动检测与一键安装更新

## 🚀 使用方法

### 源码环境运行
1. 运行 `python -m venv .venv` 创建虚拟环境。
2. 运行 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` 安装依赖。
3. 运行 `.\.venv\Scripts\python.exe main.py` 启动应用，并在系统托盘中找到 BankBin 图标。

### 一键打包与发布
在根目录双击运行 `build_root_exe.bat` 脚本。脚本会自动准备独立的 `.build_venv` 构建环境。
打包完成后，单文件程序会保存在 `BankBin_Releases` 文件夹，并按 `BankBin_001.exe`、`BankBin_002.exe` 的格式自动递增编号。历史版本不会被删除或覆盖。

### 版本更新

软件启动后及运行期间会定时读取仓库中的更新清单；GitHub Releases API 仅作为后备。发现高于当前版本的新版本时，系统托盘右键菜单的“更新”栏目会显示“点击下载并安装”。点击后软件会直接下载 Release 的 EXE、校验清单中的 SHA-256 摘要，由临时更新器在旧程序退出后替换原 EXE 并启动新版本；下载或校验失败时旧程序继续运行。发布地址统一使用 [mountopjh/BankBin Releases](https://github.com/mountopjh/BankBin/releases)。

## 💡 技术说明
本项目依赖本地 SQLite 存储 (`bin_database.db`) 与阿里云支付宝 API 兜底，以及通过爬虫查询的云端兜底。登录窗口仅作为本地进入软件的入口，不连接后台，也不校验账号密码。运行时数据库、配置 (`settings.json`) 与崩溃日志统一保存在 `%APPDATA%\BankBin`，EXE 同目录仅作为只读资源位置。

---
## [2026-03-11] 最近更新说明

### 监听与快捷键
- `F6` 现在用于 **切换监听开关**（开/关），不再直接触发查询。
- 监听增加“双通道”：`pynput hook + 轮询兜底`，提升在 WPS 场景下的稳定性。
- 新增“监听诊断面板”：可查看前台窗口信息、WPS判定结果、点击捕获与剪贴板提取日志。

### WPS 捕获优化
- 鼠标点击后不再仅做单次复制，改为多次重试（`Ctrl+C` / `Ctrl+Insert` / 延迟补读）。
- 卡号提取改为“合法候选规则”，避免把杂乱文本拼成超长数字误判。

### BIN 码库同步
- 同步跟踪路径已改为 `bin_database.db`，不再使用 `bank2025.2`。
- BIN 网页查看链接：
  - `https://github.com/mountopjh/BankBin/blob/main/bin_database.db`
- BIN 直链下载地址：
  - `https://raw.githubusercontent.com/mountopjh/BankBin/main/bin_database.db`

### 更新子菜单行为（版本 / BIN）
- 托盘“更新”子菜单会同时检查“版本更新”和“BIN码库更新”两类状态。
- 版本更新：发现新版本后展示版本号；点击后直接下载、校验并在旧程序退出后自动替换、启动对应 EXE。
- BIN码库更新：发现 `bin_database.db` 新提交后，可在菜单中直接同步本地 BIN 文件。
- 当只有 BIN 码库更新时，只同步 `bin_database.db`，不会触发 EXE 下载。
