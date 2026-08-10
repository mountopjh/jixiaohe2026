# 纪小盒 - 银行BIN码查询

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/mountopjh/jixiaohe2026?style=flat-square)](https://github.com/mountopjh/jixiaohe2026/stargazers)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-mountopjh-blue.svg)](https://github.com/mountopjh)

</div>

---


这是一款专用于查询银行卡 BIN 码及其归属机构的跨平台本地化工具。支持以下核心功能：
- 桌面悬浮窗快捷键查询（选中卡号一键弹出结果）
- 历史查询数据大盘面板
- Bmob 云端账号验证与数据双向同步
- GitHub 自动检测与一键下载更新

## 🚀 使用方法

### 源码环境运行
1. **安装环境**: 双击根目录下的 `一键安装环境并配置.bat` 脚本，它会自动创建虚拟环境并在 `venv` 中安装所需的全部 Python 依赖包。
2. **运行程序**: 双击 `启动程序.bat` 即可启动应用，并在电脑系统托盘中找到纪小盒图标。

### 一键打包与发布
在根目录双击运行 `一键打包exe.bat` 脚本（前提是已经跑过环境安装步奏并且拥有 `venv` 环境）。
等待进度全部走完后，会在 `dist/` 文件夹下生成一个名为 `纪小盒.exe` 的单文件可执行程序。您可以将此程序单独提取出来发送给任何人使用，纯净无依赖。

## 💡 技术说明
本项目依赖本地 SQLite 存储 (`bin_database.db`) 与阿里云支付宝 API 兜底，以及通过爬虫查询的云端兜底。跨设备静默登录配置通过同级目录下生成的 `settings.json` 进行管理与本地存储。

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
  - `https://github.com/mountopjh/jixiaohe2026/blob/main/bin_database.db`
- BIN 直链下载地址：
  - `https://raw.githubusercontent.com/mountopjh/jixiaohe2026/main/bin_database.db`

### 更新子菜单行为（版本 / BIN）
- 托盘“更新”子菜单会同时检查“版本更新”和“BIN码库更新”两类状态。
- 版本更新：发现新版本后展示版本号，并跳转 GitHub Release 下载对应 EXE。
- BIN码库更新：发现 `bin_database.db` 新提交后，可在菜单中直接同步本地 BIN 文件。
- 当只有 BIN 码库更新时，只同步 `bin_database.db`，不会触发 EXE 下载。
