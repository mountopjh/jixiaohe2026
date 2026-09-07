import ctypes
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from ctypes import wintypes
from datetime import datetime

import crash_reporter
import keyboard
import pyperclip
import requests
from PyQt6.QtCore import QEvent, QMetaObject, QObject, QPoint, QSize, QTimer, Qt, Q_ARG, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
)

from data_manager import DB_PATH
from panels.registry import build_default_registry
from query_engine import clear_all_history, get_query_history, perform_full_query
from settings_manager import load_settings, save_settings
from ui_popup import ResultPopup

sys.excepthook = crash_reporter.write_crash_log

APP_NAME = "BankBin"
APP_VERSION = "v1.7.2"
HOTKEY_DEFAULT = "f6"
DEFAULT_LOGIN_USERNAME = "bljw"
DEFAULT_LOGIN_PASSWORD = "89625727"
GITHUB_REPO = "mountopjh/BankBin"
GITHUB_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_COMMITS_API = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
BIN_TRACK_PATH = "bin_database.db"
GITHUB_BIN_RAW_DB_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{BIN_TRACK_PATH}"
GITHUB_BIN_WEB_URL = f"https://github.com/{GITHUB_REPO}/blob/main/{BIN_TRACK_PATH}"
UPDATE_INTERVAL_MS = 5 * 60 * 1000
UPDATE_DOWNLOAD_TIMEOUT = (8, 45)
UPDATE_DOWNLOAD_CHUNK_SIZE = 512 * 1024


def format_now_seconds() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp_seconds(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def format_iso_seconds(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "未知时间"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        text = text.replace("T", " ").replace("Z", "")
        return text[:19] if len(text) >= 19 else text


_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "BankBin_SingleInstance_2026")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    ctypes.windll.user32.MessageBoxW(
        None,
        "程序已在运行中。\n请先关闭已打开的程序窗口后再启动。",
        APP_NAME,
        0x40 | 0x1000,
    )
    sys.exit(0)


class GlobalSignalSender(QObject):
    # (card_number, record, cursor_pos)
    show_popup_signal = pyqtSignal(str, object, object)


class LoginDialog(QDialog):
    def __init__(self, default_username: str = "", default_password: str = "", history=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("账号登录")
        self.setFixedSize(390, 270)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self._history_users: list[str] = []
        history = history or []
        for item in history:
            if isinstance(item, dict):
                username = str(item.get("username", "")).strip()
            else:
                username = str(item or "").strip()
            if username and username not in self._history_users:
                self._history_users.append(username)

        self.setStyleSheet(
            """
            QDialog { background-color: #FFFFFF; }
            QLabel#title { color: #007ACC; font-size: 16px; font-weight: bold; }
            QLabel#sub { color: #888888; font-size: 12px; }
            QLineEdit, QComboBox {
                background-color: #F7F8FC;
                border: 1px solid #D0D3DC;
                color: #1A1A2E;
                padding: 8px 10px;
                border-radius: 5px;
                font-size: 13px;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit:focus, QComboBox:focus { border: 1.5px solid #007ACC; background-color: #FFFFFF; }
            QPushButton#login {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 9px;
            }
            QPushButton#login:hover { background-color: #1C97EA; }
            QPushButton#eye {
                min-width: 56px;
                max-width: 56px;
                border: 1px solid #D0D3DC;
                border-radius: 5px;
                background-color: #F7F8FC;
                color: #9AA0A6;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#eye:checked {
                color: #007ACC;
                border-color: #007ACC;
                background-color: #FFFFFF;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setObjectName("title")
        sub = QLabel("请输入账号与密码")
        sub.setObjectName("sub")
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #D93025; font-size: 12px; font-weight: bold;")
        self.lbl_error.hide()

        self.input_user = QComboBox()
        self.input_user.setEditable(True)
        self.input_user.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for username in self._history_users:
            self.input_user.addItem(username)
        if default_username and default_username not in self._history_users:
            self.input_user.addItem(default_username)
        self.input_user.setCurrentText(default_username)
        if self.input_user.lineEdit() is not None:
            self.input_user.lineEdit().setPlaceholderText("账号")
        self.input_user.currentTextChanged.connect(self._on_user_changed)

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.setPlaceholderText("密码")
        self.input_pass.setText(default_password)
        self.btn_eye = QPushButton("")
        self.btn_eye.setObjectName("eye")
        self.btn_eye.setCheckable(True)
        self.btn_eye.setToolTip("显示/隐藏密码")
        self._eye_icon_visible = self._load_eye_icon(["view-visible", "password-show-on", "visibility"])
        self._eye_icon_hidden = self._load_eye_icon(["view-hidden", "password-show-off", "visibility-off"])
        self._has_eye_icons = not self._eye_icon_visible.isNull() and not self._eye_icon_hidden.isNull()
        self.btn_eye.setIconSize(QSize(16, 16))
        if self._has_eye_icons:
            self.btn_eye.setIcon(self._eye_icon_hidden)
            self.btn_eye.setText("")
            self.btn_eye.setToolTip("显示密码")
        else:
            self.btn_eye.setText("可见")
            self.btn_eye.setToolTip("显示密码")
        self.btn_eye.toggled.connect(self._toggle_password_visible)

        btn_login = QPushButton("登录")
        btn_login.setObjectName("login")

        pass_row = QHBoxLayout()
        pass_row.setSpacing(6)
        pass_row.addWidget(self.input_pass)
        pass_row.addWidget(self.btn_eye)

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.lbl_error)
        layout.addWidget(self.input_user)
        layout.addLayout(pass_row)
        layout.addWidget(btn_login)

        btn_login.clicked.connect(self._do_accept)
        self.input_pass.returnPressed.connect(self._do_accept)

    def _on_user_changed(self, username: str):
        self.input_pass.clear()

    def _load_eye_icon(self, names):
        for name in names:
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
        return QIcon()

    def _toggle_password_visible(self, checked: bool):
        self.input_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        if self._has_eye_icons:
            self.btn_eye.setIcon(self._eye_icon_visible if checked else self._eye_icon_hidden)
            self.btn_eye.setText("")
        else:
            self.btn_eye.setText("不可见" if checked else "可见")
        self.btn_eye.setToolTip("隐藏密码" if checked else "显示密码")

    def _do_accept(self):
        user, password = self.credentials()
        if not user or not password:
            self.lbl_error.setText("账号或密码不能为空")
            self.lbl_error.show()
            return
        self.accept()

    def credentials(self):
        return self.input_user.currentText().strip(), self.input_pass.text().strip()


class HotkeySettingDialog(QDialog):
    def __init__(self, current_hotkey: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("监听快捷键设置")
        self.setFixedSize(380, 180)
        self._recording = False

        self.setStyleSheet(
            """
            QDialog { background-color: #FFFFFF; }
            QLabel { color: #1A1A2E; font-family: 'Microsoft YaHei'; }
            QLineEdit {
                background-color: #F7F8FC;
                border: 1px solid #D0D3DC;
                border-radius: 5px;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #c8cbda;
                border-radius: 6px;
                padding: 6px 14px;
                color: #1a1a2e;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #eef0f8; border-color: #007acc; color: #007acc; }
            QPushButton#ok { background-color: #007ACC; color: #FFFFFF; border: none; }
            QPushButton#ok:hover { background-color: #1C97EA; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(QLabel("支持手动输入，也可以点击“录入按键”后直接按下快捷键。"))

        row = QHBoxLayout()
        self.input_hotkey = QLineEdit(current_hotkey.upper() if current_hotkey else "F6")
        self.input_hotkey.installEventFilter(self)
        self.btn_record = QPushButton("录入按键")
        self.btn_record.clicked.connect(self.toggle_recording)
        row.addWidget(self.input_hotkey)
        row.addWidget(self.btn_record)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addStretch()
        btn_ok = QPushButton("保存")
        btn_ok.setObjectName("ok")
        btn_cancel = QPushButton("取消")
        row2.addWidget(btn_ok)
        row2.addWidget(btn_cancel)
        layout.addLayout(row2)

        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)

    @staticmethod
    def normalize_hotkey_text(text: str) -> str:
        text = (text or "").strip().lower().replace(" ", "")
        return text or HOTKEY_DEFAULT

    def toggle_recording(self):
        self._recording = not self._recording
        if self._recording:
            self.btn_record.setText("按下快捷键...")
            self.input_hotkey.setFocus()
        else:
            self.btn_record.setText("录入按键")

    def _event_to_hotkey(self, event) -> str:
        key = event.key()
        if key in {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta}:
            return ""

        parts = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        key_text = QKeySequence(key).toString().lower().strip()
        if not key_text:
            return ""
        parts.append(key_text.replace("+", ""))
        return "+".join(parts)

    def eventFilter(self, watched, event):
        if watched is self.input_hotkey and self._recording and event.type() == QEvent.Type.KeyPress:
            hotkey = self._event_to_hotkey(event)
            if hotkey:
                self.input_hotkey.setText(hotkey.upper())
                self._recording = False
                self.btn_record.setText("录入按键")
            return True
        return super().eventFilter(watched, event)

    def _accept(self):
        value = self.normalize_hotkey_text(self.input_hotkey.text())
        self.input_hotkey.setText(value.upper())
        self.accept()

    def value(self) -> str:
        return self.normalize_hotkey_text(self.input_hotkey.text())


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在加载")
        self.setFixedSize(500, 290)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        self.setStyleSheet(
            """
            QDialog { background-color: #FFFFFF; }
            QLabel#title { color: #007ACC; font-size: 16px; font-weight: bold; font-family: 'Microsoft YaHei'; }
            QLabel#status { color: #1A1A2E; font-size: 13px; font-family: 'Microsoft YaHei'; }
            QProgressBar {
                border: 1px solid #d0d3dc;
                border-radius: 6px;
                background: #f7f8fc;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk { background-color: #007ACC; border-radius: 5px; }
            QTextEdit {
                border: 1px solid #dde1ec;
                border-radius: 6px;
                background: #fbfcff;
                color: #1A1A2E;
                font-family: Consolas, 'Microsoft YaHei';
                font-size: 12px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.lbl_title = QLabel("程序加载中...")
        self.lbl_title.setObjectName("title")
        self.lbl_status = QLabel("准备加载")
        self.lbl_status.setObjectName("status")
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress)
        layout.addWidget(self.log)

    def update_step(self, percent: int, message: str, file_name: str = ""):
        percent = max(0, min(100, int(percent)))
        self.progress.setValue(percent)
        self.lbl_status.setText(message)
        line = f"[{format_now_seconds()}] {message}"
        if file_name:
            line += f" -> {file_name}"
        self.log.append(line)


class ListenerDebugDialog(QDialog):
    def __init__(self, app_ref, parent=None):
        super().__init__(parent)
        self._app_ref = app_ref
        self._last_seq = 0

        self.setWindowTitle("监听诊断面板")
        self.setFixedSize(760, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self.setStyleSheet(
            """
            QDialog { background-color: #FFFFFF; }
            QLabel { color: #1A1A2E; font-family: 'Microsoft YaHei'; font-size: 12px; }
            QLabel#title { color: #007ACC; font-size: 16px; font-weight: bold; }
            QTextEdit {
                border: 1px solid #D0D3DC;
                border-radius: 6px;
                background-color: #FBFCFF;
                font-family: Consolas, 'Microsoft YaHei';
                font-size: 12px;
                color: #1A1A2E;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #c8cbda;
                border-radius: 6px;
                padding: 6px 14px;
                color: #1a1a2e;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #eef0f8; border-color: #007acc; color: #007acc; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("监听诊断面板")
        title.setObjectName("title")
        self.lbl_runtime = QLabel("-")
        self.lbl_foreground = QLabel("-")
        self.lbl_last = QLabel("-")
        self.lbl_runtime.setWordWrap(True)
        self.lbl_foreground.setWordWrap(True)
        self.lbl_last.setWordWrap(True)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_clear = QPushButton("清空日志")
        self.btn_copy = QPushButton("复制日志")
        self.btn_close = QPushButton("关闭")
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_copy)
        btn_row.addWidget(self.btn_close)

        layout.addWidget(title)
        layout.addWidget(self.lbl_runtime)
        layout.addWidget(self.lbl_foreground)
        layout.addWidget(self.lbl_last)
        layout.addWidget(self.txt_log)
        layout.addLayout(btn_row)

        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_close.clicked.connect(self.close)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def ensure_active(self):
        if not self._timer.isActive():
            self._timer.start()
        self._refresh()

    def _on_clear(self):
        self._app_ref._clear_listener_debug_logs()
        self._last_seq = 0
        self.txt_log.clear()
        self._refresh()

    def _on_copy(self):
        self._app_ref.clipboard().setText(self.txt_log.toPlainText())

    def _refresh(self):
        snapshot = self._app_ref._get_listener_debug_snapshot()
        self.lbl_runtime.setText(
            "运行状态："
            f"监听开关={snapshot.get('is_listening')}  |  "
            f"轮询定时器={snapshot.get('polling_active')}  |  "
            f"鼠标钩子={snapshot.get('mouse_hook_running')}  |  "
            f"快捷键={snapshot.get('hotkey')}"
        )
        self.lbl_foreground.setText(
            "前台窗口："
            f"EXE={snapshot.get('exe_name')}  |  "
            f"Class={snapshot.get('class_name')}  |  "
            f"标题={snapshot.get('title')}  |  "
            f"WPS表格判定={snapshot.get('is_wps_sheet')}"
        )
        self.lbl_last.setText(
            "最近事件："
            f"上次点击时间={snapshot.get('last_click_time')}  |  "
            f"按钮按下态={snapshot.get('mouse_button_down')}"
        )

        rows = self._app_ref._get_listener_debug_logs_since(self._last_seq)
        if rows:
            for seq, line in rows:
                self.txt_log.append(line)
                self._last_seq = max(self._last_seq, seq)
            self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


class BinApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self.settings = {}
        self.hotkey = HOTKEY_DEFAULT
        self.is_listening = True
        self._hotkey_handle = None
        self._mouse_listener = None
        self._update_lock = threading.Lock()
        self._latest_release_version = ""
        self._latest_release_url = ""
        self._latest_release_sha256 = ""
        self._update_installing = False
        self._latest_bin_sha = ""
        self._listener_error_notified = False
        self._debug_lock = threading.Lock()
        self._listener_debug_logs: list[tuple[int, str]] = []
        self._listener_debug_seq = 0
        self._listener_debug_dialog = None
        self._last_hotkey_toggle_ts = 0.0
        self._mouse_poll_timer = QTimer(self)
        self._mouse_poll_timer.setInterval(45)
        self._mouse_poll_timer.timeout.connect(self._poll_mouse_left_click)
        self._mouse_button_down = False
        self._last_click_ts = 0.0

        self.signal_sender = GlobalSignalSender()
        self.signal_sender.show_popup_signal.connect(self.display_popup)

        self.panel_registry = None
        self.main_panel = None
        self.popup = None

        self._loading = LoadingDialog()
        self._loading.show()
        self.processEvents()

        self._loading.update_step(8, "加载配置", "settings.json")
        self.settings = load_settings() or {}
        self._normalize_settings()
        save_settings(self.settings)
        self.hotkey = self._normalize_hotkey(self.settings.get("hotkey", HOTKEY_DEFAULT))
        self.is_listening = bool(self.settings.get("listen_enabled", True))

        self._loading.update_step(22, "初始化界面", "ui_popup.py")
        self.panel_registry = build_default_registry(self.signal_sender)
        self.main_panel = self.panel_registry.get_primary_widget()
        self.popup = ResultPopup()

        self._loading.update_step(38, "准备登录", "local")
        self._loading.hide()
        if not self._show_login_dialog():
            self.quit()
            return
        self._loading.show()
        self.processEvents()

        self._loading.update_step(58, "应用首次运行策略", "query_history")
        self._apply_first_run_policy()
        self._refresh_user_context()

        self._loading.update_step(78, "创建托盘菜单", "main.py")
        self.init_tray()

        self._loading.update_step(92, "启动监听服务", f"hotkey={self.hotkey.upper()}")
        self.restart_monitoring_state()

        self._loading.update_step(100, "加载完成")
        self.processEvents()
        QTimer.singleShot(350, self._loading.close)

    def _normalize_settings(self):
        history = self.settings.get("login_history", [])
        normalized_history = []
        seen_users = set()
        if isinstance(history, list):
            for item in history:
                if isinstance(item, dict):
                    username = str(item.get("username", "")).strip()
                else:
                    username = str(item or "").strip()
                if not username or username in seen_users:
                    continue
                normalized_history.append({"username": username})
                seen_users.add(username)
                if len(normalized_history) >= 20:
                    break
        self.settings["login_history"] = normalized_history
        for key in ("password", "firebase_id_token", "firebase_refresh_token", "firebase_local_id"):
            self.settings.pop(key, None)
        if not self.settings.get("hotkey"):
            self.settings["hotkey"] = HOTKEY_DEFAULT
        if "listen_enabled" not in self.settings:
            self.settings["listen_enabled"] = True

    def _normalize_hotkey(self, value: str) -> str:
        return HotkeySettingDialog.normalize_hotkey_text(value)

    def _remember_login_history(self, username: str):
        username = (username or "").strip()
        if not username:
            return

        history = self.settings.get("login_history", [])
        new_history = [{"username": username}]
        for item in history:
            if isinstance(item, dict):
                old_user = str(item.get("username", "")).strip()
            else:
                old_user = str(item or "").strip()
            if not old_user or old_user == username:
                continue
            new_history.append({"username": old_user})
            if len(new_history) >= 20:
                break

        self.settings["login_history"] = new_history
        self.settings["username"] = username
        for key in ("password", "firebase_id_token", "firebase_refresh_token", "firebase_local_id"):
            self.settings.pop(key, None)

    def _show_login_dialog(self) -> bool:
        user = DEFAULT_LOGIN_USERNAME
        history = self.settings.get("login_history", [])

        dlg = LoginDialog(user, DEFAULT_LOGIN_PASSWORD, history)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False

        user, _password = dlg.credentials()
        self._remember_login_history(user)
        save_settings(self.settings)
        return True

    def _apply_first_run_policy(self):
        if not self.settings.get("first_run_done", False):
            clear_all_history()
            self.settings["first_run_done"] = True
            save_settings(self.settings)

    def _refresh_user_context(self):
        username = str(self.settings.get("username", "") or DEFAULT_LOGIN_USERNAME).strip()
        if self.main_panel is not None:
            self.main_panel.setWindowTitle(f"{APP_NAME} - 当前账号：{username}")
        if hasattr(self, "action_user"):
            self.action_user.setText(f"账号：{username}")

    def _debug_log_listener(self, message: str):
        line = f"[{format_now_seconds()}] {message}"
        with self._debug_lock:
            self._listener_debug_seq += 1
            self._listener_debug_logs.append((self._listener_debug_seq, line))
            if len(self._listener_debug_logs) > 600:
                self._listener_debug_logs = self._listener_debug_logs[-600:]

    def _clear_listener_debug_logs(self):
        with self._debug_lock:
            self._listener_debug_logs.clear()
            self._listener_debug_seq = 0

    def _get_listener_debug_logs_since(self, last_seq: int):
        with self._debug_lock:
            return [item for item in self._listener_debug_logs if item[0] > last_seq]

    def _get_listener_debug_snapshot(self):
        hwnd, title, class_name, exe_name = self._get_foreground_window_info()
        is_wps_sheet = self._is_wps_window_info(title, class_name, exe_name)
        click_time = "-" if not self._last_click_ts else format_timestamp_seconds(self._last_click_ts)
        return {
            "is_listening": self.is_listening,
            "polling_active": self._mouse_poll_timer.isActive(),
            "mouse_hook_running": bool(self._mouse_listener and self._mouse_listener.running),
            "hotkey": self.hotkey.upper(),
            "title": title,
            "class_name": class_name,
            "exe_name": exe_name,
            "is_wps_sheet": is_wps_sheet,
            "last_click_time": click_time,
            "mouse_button_down": self._mouse_button_down,
            "hwnd": hwnd,
        }

    def _build_icon(self, text_color: str, bg_color: str) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(bg_color))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(0, 0, 32, 32, 8, 8)
        painter.setPen(QColor(text_color))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Bin")
        painter.end()
        return QIcon(pixmap)

    def init_tray(self):
        self.icon_normal = self._build_icon("#007ACC", "#FFFFFF")
        self.icon_gray = self._build_icon("#7A7A7A", "#E0E0E0")
        self.tray_icon = QSystemTrayIcon(self.icon_normal, self)

        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet(
            """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #D0D3DC;
                border-radius: 8px;
                padding: 4px 0px;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
                color: #1A1A2E;
            }
            QMenu::item {
                padding: 9px 28px 9px 18px;
                margin: 1px 4px;
                border-radius: 5px;
                color: #1A1A2E;
            }
            QMenu::item:selected { background-color: #E8F0FE; color: #007ACC; }
            QMenu::item:disabled { color: #999999; }
            QMenu::separator { height: 1px; background: #E0E3EE; margin: 4px 10px; }
            """
        )

        self.account_menu = QMenu("当前账号", self.tray_menu)
        self.action_user = self.account_menu.addAction(
            f"账号：{self.settings.get('username', DEFAULT_LOGIN_USERNAME) or '--'}"
        )
        self.action_user.setEnabled(False)
        self.action_switch_account = self.account_menu.addAction("切换账号")
        self.action_switch_account.triggered.connect(self.switch_account)
        self.tray_menu.addMenu(self.account_menu)

        self.tray_menu.addSeparator()

        self.api_menu = QMenu("查询网站", self.tray_menu)
        for site in [
            "1. 支付宝接口 (https://ccdcapi.alipay.com/validateAndCacheCardInfo.json)",
            "2. CardBin (https://cardbin.cn)",
        ]:
            action = self.api_menu.addAction(site)
            action.setEnabled(False)
        self.tray_menu.addMenu(self.api_menu)

        self.tray_menu.addSeparator()

        self.recent_menu = QMenu("最近查询", self.tray_menu)
        self.tray_menu.addMenu(self.recent_menu)
        self.tray_menu.aboutToShow.connect(self.update_recent_menu)

        self.tray_menu.addSeparator()

        self.action_show = self.tray_menu.addAction("打开程序窗口")
        self.action_show.triggered.connect(self.show_main_panel)

        self.panel_menu = QMenu("Panels", self.tray_menu)
        if self.panel_registry is not None:
            for panel_id in self.panel_registry.panel_ids():
                panel = self.panel_registry.get_panel(panel_id)
                action = self.panel_menu.addAction(panel.panel_name)
                action.triggered.connect(lambda checked, pid=panel_id: self.show_panel(pid))
        self.tray_menu.addMenu(self.panel_menu)

        self.tray_menu.addSeparator()

        self.monitor_menu = QMenu("监听设置", self.tray_menu)
        self.action_toggle = self.monitor_menu.addAction("")
        self.action_toggle.triggered.connect(self._toggle_monitoring)
        self.action_hotkey = self.monitor_menu.addAction("监听快捷键设置")
        self.action_hotkey.triggered.connect(self.open_hotkey_setting_dialog)
        self.action_listener_debug = self.monitor_menu.addAction("监听诊断面板")
        self.action_listener_debug.triggered.connect(self.open_listener_debug_dialog)
        self.tray_menu.addMenu(self.monitor_menu)
        self._update_toggle_action_text()

        self.tray_menu.addSeparator()

        self.update_menu = QMenu("更新", self.tray_menu)
        self.action_version_update = self.update_menu.addAction("版本更新：检查中...")
        self.action_version_update.setEnabled(False)
        self.action_bin_update = self.update_menu.addAction("BIN码库：检查中...")
        self.action_bin_update.setEnabled(False)
        self.action_check_update_now = self.update_menu.addAction("立即检查更新")
        self.action_check_update_now.triggered.connect(self.trigger_update_check)
        self.action_sync_bin_now = self.update_menu.addAction("同步BIN码库")
        self.action_sync_bin_now.triggered.connect(self.sync_bin_database)
        self.tray_menu.addMenu(self.update_menu)

        self.tray_menu.addSeparator()

        self.about_menu = QMenu(f"关于 - {APP_NAME} {APP_VERSION.upper()}", self.tray_menu)
        self.act_curr_ver = self.about_menu.addAction(f"当前版本: {APP_VERSION.upper()}")
        self.act_curr_ver.setEnabled(False)
        self.tray_menu.addMenu(self.about_menu)

        self.action_time = self.tray_menu.addAction("更新时间: 2026-09-07")
        self.action_time.setEnabled(False)

        self.tray_menu.addSeparator()

        self.action_quit = self.tray_menu.addAction("退出")
        self.action_quit.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.setToolTip(APP_NAME)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(UPDATE_INTERVAL_MS)
        self.update_timer.timeout.connect(self.trigger_update_check)
        self.update_timer.start()
        self.trigger_update_check()

    def _parse_version(self, version_text: str):
        nums = [int(x) for x in re.findall(r"\d+", version_text or "")]
        return tuple(nums) if nums else (0,)

    def _is_newer_version(self, latest: str, current: str) -> bool:
        lv = list(self._parse_version(latest))
        cv = list(self._parse_version(current))
        size = max(len(lv), len(cv))
        lv.extend([0] * (size - len(lv)))
        cv.extend([0] * (size - len(cv)))
        return tuple(lv) > tuple(cv)

    def trigger_update_check(self):
        if self._update_lock.locked():
            return
        threading.Thread(target=self._check_github_updates, daemon=True).start()

    def _check_github_updates(self):
        if not self._update_lock.acquire(blocking=False):
            return
        try:
            self._check_release_update()
            self._check_bin_update()
        finally:
            self._update_lock.release()

    def _check_release_update(self):
        try:
            resp = requests.get(GITHUB_RELEASE_API, timeout=7)
            if resp.status_code != 200:
                return
            data = resp.json() or {}
            latest_version = str(data.get("tag_name", "")).strip().lower()
            release_url = ""
            release_sha256 = ""
            for asset in data.get("assets", []):
                name = str(asset.get("name", "")).lower()
                if name.endswith(".exe"):
                    release_url = str(asset.get("browser_download_url", "")).strip()
                    digest = str(asset.get("digest", "")).strip().lower()
                    if digest.startswith("sha256:"):
                        release_sha256 = digest.split(":", 1)[1]
                    break

            if latest_version and release_url and self._is_newer_version(latest_version, APP_VERSION):
                QMetaObject.invokeMethod(
                    self,
                    "on_version_update_found",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, latest_version),
                    Q_ARG(str, release_url),
                    Q_ARG(str, release_sha256),
                )
            else:
                QMetaObject.invokeMethod(
                    self,
                    "on_version_update_checked",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, latest_version or APP_VERSION),
                )
        except Exception:
            return

    def _check_bin_update(self):
        try:
            resp = requests.get(GITHUB_COMMITS_API, params={"path": BIN_TRACK_PATH, "per_page": 1}, timeout=7)
            if resp.status_code != 200:
                return
            rows = resp.json() or []
            if not rows:
                return

            latest = rows[0]
            latest_sha = str(latest.get("sha", "")).strip()
            latest_url = str(latest.get("html_url", "")).strip() or GITHUB_BIN_WEB_URL
            commit_obj = latest.get("commit") or {}
            latest_msg = str(commit_obj.get("message", "")).strip()
            latest_date = str((commit_obj.get("author") or {}).get("date", "")).strip()
            if not latest_sha:
                return

            if not self.settings.get("last_seen_bin_sha"):
                self.settings["last_seen_bin_sha"] = latest_sha
                save_settings(self.settings)

            self._latest_bin_sha = latest_sha
            seen_sha = str(self.settings.get("last_seen_bin_sha", "")).strip()
            if latest_sha != seen_sha:
                QMetaObject.invokeMethod(
                    self,
                    "on_bin_update_found",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, latest_sha),
                    Q_ARG(str, latest_msg),
                    Q_ARG(str, latest_url),
                    Q_ARG(str, latest_date),
                )
            else:
                QMetaObject.invokeMethod(
                    self,
                    "on_bin_update_checked",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, latest_sha),
                )
        except Exception:
            return

    @pyqtSlot(str, str, str)
    def on_version_update_found(self, latest_version: str, release_url: str, release_sha256: str):
        if self._update_installing:
            return
        self._latest_release_version = latest_version
        self._latest_release_url = release_url
        self._latest_release_sha256 = release_sha256
        self.action_version_update.setText(f"版本更新：发现 {latest_version.upper()}（点击下载并安装）")
        self.action_version_update.setEnabled(True)
        try:
            self.action_version_update.triggered.disconnect()
        except Exception:
            pass
        self.action_version_update.triggered.connect(self.install_available_update)
        self.tray_icon.showMessage(
            "版本更新",
            f"发现新版本 {latest_version.upper()}，点击菜单将自动下载并安装。",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    @pyqtSlot(str)
    def on_version_update_checked(self, latest_version: str):
        if self._update_installing:
            return
        latest_version = (latest_version or APP_VERSION).upper()
        self.action_version_update.setText(f"版本更新：当前已是最新（{latest_version}）")
        self.action_version_update.setEnabled(False)

    def install_available_update(self):
        if self._update_installing:
            return
        if not self._latest_release_url:
            QMessageBox.warning(None, "自动更新", "未获取到新版本安装包，请稍后重新检查更新。")
            return
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                None,
                "自动更新",
                "当前为源代码运行环境，不能替换 Python 解释器。将打开新版本下载地址。",
            )
            webbrowser.open(self._latest_release_url)
            return

        self._update_installing = True
        self.action_version_update.setText("版本更新：正在下载…")
        self.action_version_update.setEnabled(False)
        self.tray_icon.showMessage(
            "版本更新",
            "正在下载新版本，下载完成后将自动关闭旧程序并启动新版本。",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )
        threading.Thread(
            target=self._download_and_prepare_update,
            args=(self._latest_release_url, self._latest_release_sha256),
            daemon=True,
            name="BankBinUpdateDownloader",
        ).start()

    def _download_and_prepare_update(self, download_url: str, expected_sha256: str):
        update_dir = ""
        download_path = ""
        helper_path = ""
        try:
            target_path = os.path.abspath(sys.executable)
            if not target_path.lower().endswith(".exe"):
                raise RuntimeError("当前运行文件不是可更新的 EXE。")

            update_dir = tempfile.mkdtemp(prefix="bankbin_update_")
            download_path = os.path.join(update_dir, "BankBin_update.exe")
            hasher = hashlib.sha256()
            downloaded = 0
            last_percent = -1

            with requests.get(download_url, stream=True, timeout=UPDATE_DOWNLOAD_TIMEOUT) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", "0") or 0)
                with open(download_path, "wb") as file:
                    for chunk in resp.iter_content(chunk_size=UPDATE_DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        file.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = min(99, int(downloaded * 100 / total))
                            if percent != last_percent:
                                last_percent = percent
                                QMetaObject.invokeMethod(
                                    self,
                                    "on_update_download_progress",
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(int, percent),
                                )

            if downloaded < 4096:
                raise RuntimeError("下载的安装包过小，已停止更新。")
            with open(download_path, "rb") as file:
                if file.read(2) != b"MZ":
                    raise RuntimeError("下载内容不是有效的 Windows 安装包。")

            actual_sha256 = hasher.hexdigest().lower()
            expected_sha256 = re.sub(r"^sha256:", "", expected_sha256 or "", flags=re.IGNORECASE).lower()
            if expected_sha256 and actual_sha256 != expected_sha256:
                raise RuntimeError("安装包 SHA-256 校验失败，已停止更新。")

            helper_path = self._write_update_helper(download_path, target_path)
            QMetaObject.invokeMethod(
                self,
                "on_update_download_ready",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, helper_path),
            )
        except Exception as exc:
            for path in (helper_path, download_path):
                try:
                    if path and os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
            try:
                if update_dir and os.path.isdir(update_dir):
                    os.rmdir(update_dir)
            except OSError:
                pass
            QMetaObject.invokeMethod(
                self,
                "on_update_install_failed",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, str(exc)),
            )

    @staticmethod
    def _batch_path_value(path: str) -> str:
        return os.path.abspath(path).replace("%", "%%")

    def _write_update_helper(self, download_path: str, target_path: str) -> str:
        helper_path = os.path.join(os.path.dirname(download_path), "install_update.cmd")
        source_value = self._batch_path_value(download_path)
        target_value = self._batch_path_value(target_path)
        script = "\r\n".join(
            [
                "@echo off",
                "setlocal EnableExtensions DisableDelayedExpansion",
                f'set "SOURCE={source_value}"',
                f'set "TARGET={target_value}"',
                "set /a ATTEMPTS=0",
                ":copy_again",
                'copy /Y "%SOURCE%" "%TARGET%" >nul',
                "if not errorlevel 1 goto start_app",
                "set /a ATTEMPTS+=1",
                "if %ATTEMPTS% GEQ 30 goto start_from_download",
                "timeout /t 1 /nobreak >nul",
                "goto copy_again",
                ":start_app",
                'start "" "%TARGET%"',
                'del "%SOURCE%" >nul 2>nul',
                'del "%~f0" >nul 2>nul',
                "exit /b 0",
                ":start_from_download",
                'start "" "%SOURCE%"',
                'del "%~f0" >nul 2>nul',
                "exit /b 1",
                "",
            ]
        )
        with open(helper_path, "w", encoding="mbcs", newline="") as file:
            file.write(script)
        return helper_path

    @pyqtSlot(int)
    def on_update_download_progress(self, percent: int):
        if self._update_installing:
            self.action_version_update.setText(f"版本更新：正在下载 {percent}%")

    @pyqtSlot(str)
    def on_update_download_ready(self, helper_path: str):
        try:
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            subprocess.Popen(
                ["cmd.exe", "/c", helper_path],
                cwd=os.path.dirname(helper_path),
                close_fds=True,
                creationflags=creationflags,
            )
        except Exception as exc:
            self.on_update_install_failed(str(exc))
            return

        self.action_version_update.setText("版本更新：正在安装并重启…")
        self.tray_icon.showMessage(
            "版本更新",
            "新版本已准备完成，正在关闭旧程序并启动新版本。",
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )
        QTimer.singleShot(350, self.quit_app)

    @pyqtSlot(str)
    def on_update_install_failed(self, message: str):
        self._update_installing = False
        version = (self._latest_release_version or "新版本").upper()
        self.action_version_update.setText(f"版本更新：发现 {version}（点击重试）")
        self.action_version_update.setEnabled(True)
        QMessageBox.warning(None, "自动更新失败", f"未替换当前程序，旧版本仍在运行。\n\n原因：{message}")

    @pyqtSlot(str, str, str, str)
    def on_bin_update_found(self, sha: str, message: str, commit_url: str, commit_date: str):
        short_sha = sha[:8]
        self.action_bin_update.setText(f"BIN码库：发现更新 {short_sha}（点击处理）")
        self.action_bin_update.setEnabled(True)
        try:
            self.action_bin_update.triggered.disconnect()
        except Exception:
            pass

        def _open_or_sync():
            answer = QMessageBox.question(
                None,
                "BIN码库更新",
                f"发现 BIN 码库更新\n提交: {short_sha}\n\n是否立即同步到本地？\n选择“否”将打开 GitHub 查看详情。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.sync_bin_database()
            else:
                webbrowser.open(commit_url or GITHUB_BIN_WEB_URL)

        self.action_bin_update.triggered.connect(_open_or_sync)

        notified_sha = str(self.settings.get("last_notified_bin_sha", "")).strip()
        if notified_sha != sha:
            self.settings["last_notified_bin_sha"] = sha
            save_settings(self.settings)
            update_time = format_iso_seconds(commit_date)
            msg_preview = message.split("\n", 1)[0] if message else ""
            self.tray_icon.showMessage(
                "BIN码库更新",
                f"发现新提交 {short_sha}（{update_time}）\n{msg_preview}",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )

    @pyqtSlot(str)
    def on_bin_update_checked(self, sha: str):
        short_sha = (sha or "")[:8]
        self.action_bin_update.setText(f"BIN码库：暂无更新（{short_sha or 'latest'}）")
        self.action_bin_update.setEnabled(False)

    def sync_bin_database(self):
        try:
            resp = requests.get(GITHUB_BIN_RAW_DB_URL, timeout=18)
            if resp.status_code != 200 or not resp.content:
                raise RuntimeError(f"下载失败，状态码: {resp.status_code}")

            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="bin_db_", suffix=".db", dir=os.path.dirname(DB_PATH))
            os.close(fd)
            try:
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
                os.replace(tmp_path, DB_PATH)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if self._latest_bin_sha:
                self.settings["last_seen_bin_sha"] = self._latest_bin_sha
            save_settings(self.settings)

            if self.main_panel is not None:
                self.main_panel.load_history()
            QMessageBox.information(None, "同步完成", "BIN码库已同步到本地。")
            self.trigger_update_check()
        except Exception as exc:
            QMessageBox.warning(None, "同步失败", f"同步 BIN 码库失败：{exc}")
            webbrowser.open(GITHUB_BIN_WEB_URL)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_panel()

    def _bring_window_to_front(self, widget):
        if widget is None:
            return
        if widget.isMinimized():
            widget.showNormal()
        widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        widget.show()
        widget.raise_()
        widget.activateWindow()

        def _unset_topmost():
            if widget and not widget.isHidden():
                widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
                widget.show()

        QTimer.singleShot(220, _unset_topmost)

    def show_panel(self, panel_id: str):
        panel = self.panel_registry.get_panel(panel_id) if self.panel_registry else None
        if panel is None:
            return
        panel.refresh()
        self._bring_window_to_front(panel.get_widget())

    def show_main_panel(self):
        primary_id = self.panel_registry.get_primary_id() if self.panel_registry else None
        if primary_id:
            self.show_panel(primary_id)

    def quit_app(self):
        try:
            if hasattr(self, "update_timer"):
                self.update_timer.stop()
        except Exception:
            pass
        self._stop_mouse_polling()
        self._stop_mouse_listener()
        self._unregister_hotkey_listener()
        if self._listener_debug_dialog is not None:
            self._listener_debug_dialog.close()
        self.tray_icon.hide()
        self.quit()

    def update_recent_menu(self):
        self.recent_menu.clear()
        history = get_query_history(success_only=True)[:20]
        if not history:
            self.recent_menu.addAction("暂无查询记录").setEnabled(False)
            return
        for row in history:
            card_no = row.get("card_no", "") or ""
            bank = row.get("bank_name", "") or "未知银行"
            card_type = row.get("card_type", "") or ""
            card_length = row.get("card_length", "") or "-"
            source = row.get("source", "") or ""
            text = f"{card_no} | {bank} [{card_type}] 长度:{card_length} ({source})"
            action = self.recent_menu.addAction(text)
            action.triggered.connect(lambda checked, num=card_no: self.do_manual_query(num))

    def do_manual_query(self, card_number: str):
        def _do_query():
            record = perform_full_query(card_number, self.signal_sender)
            self.signal_sender.show_popup_signal.emit(card_number, record, None)

        threading.Thread(target=_do_query, daemon=True).start()

    def switch_account(self):
        if not self._show_login_dialog():
            QMessageBox.information(None, "提示", "未重新登录，程序将退出。")
            self.quit_app()
            return
        self._refresh_user_context()
        if self.main_panel is not None:
            self.main_panel.load_history()
        self.show_main_panel()

    def open_hotkey_setting_dialog(self):
        dlg = HotkeySettingDialog(self.hotkey)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.hotkey = self._normalize_hotkey(dlg.value())
        self.settings["hotkey"] = self.hotkey
        save_settings(self.settings)
        if self.is_listening:
            self._register_hotkey_listener()
        self._update_toggle_action_text()
        self.tray_icon.showMessage(
            "快捷键更新",
            f"监听快捷键已设置为 {self.hotkey.upper()}",
            QSystemTrayIcon.MessageIcon.Information,
            2200,
        )

    def open_listener_debug_dialog(self):
        if self._listener_debug_dialog is None:
            self._listener_debug_dialog = ListenerDebugDialog(self)
        self._listener_debug_dialog.ensure_active()
        self._listener_debug_dialog.show()
        self._listener_debug_dialog.raise_()
        self._listener_debug_dialog.activateWindow()

    def restart_monitoring_state(self):
        self._debug_log_listener(f"重置监听状态：is_listening={self.is_listening}")
        if self.is_listening:
            self._start_mouse_polling()
            self._start_mouse_listener()
            self._register_hotkey_listener()
        else:
            self._stop_mouse_polling()
            self._stop_mouse_listener()
            self._unregister_hotkey_listener()

    def _update_toggle_action_text(self):
        if not hasattr(self, "action_toggle"):
            return
        state = "已开启" if self.is_listening else "已关闭"
        self.action_toggle.setText(f"监听开关：{state}")
        if hasattr(self, "action_hotkey"):
            self.action_hotkey.setText(f"监听快捷键设置（当前 {self.hotkey.upper()}）")

    def _toggle_monitoring(self):
        self.is_listening = not self.is_listening
        self._debug_log_listener(f"监听开关切换：is_listening={self.is_listening}")
        self.settings["listen_enabled"] = self.is_listening
        save_settings(self.settings)
        self._update_toggle_action_text()

        if self.is_listening:
            self.tray_icon.setIcon(self.icon_normal)
            self._start_mouse_polling()
            self._start_mouse_listener()
            self._register_hotkey_listener()
        else:
            self.tray_icon.setIcon(self.icon_gray)
            self._stop_mouse_polling()
            self._stop_mouse_listener()
            self._unregister_hotkey_listener()
            if self.popup and self.popup.isVisible():
                self.popup.dismiss()

    def _register_hotkey_listener(self):
        self._unregister_hotkey_listener()
        hotkey_text = self._normalize_hotkey(self.hotkey)
        try:
            self._hotkey_handle = keyboard.add_hotkey(
                hotkey_text,
                self._on_hotkey_trigger,
                suppress=False,
                trigger_on_release=True,
            )
            self._debug_log_listener(f"热键监听已注册：{hotkey_text.upper()}")
        except Exception as exc:
            self._hotkey_handle = None
            self._debug_log_listener(f"热键监听注册失败：{exc}")
            print(f"Hotkey listener register failed: {exc}")

    def _unregister_hotkey_listener(self):
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except Exception:
                pass
        self._hotkey_handle = None

    def _on_hotkey_trigger(self):
        now = time.time()
        if now - self._last_hotkey_toggle_ts < 0.4:
            return
        self._last_hotkey_toggle_ts = now
        self._debug_log_listener("[hotkey] 触发：切换监听开关")
        self._toggle_monitoring()

    def _extract_candidate_card_number(self, text: str) -> str:
        text = str(text or "")
        if not text:
            return ""

        # 1) Prefer direct continuous digit groups.
        direct = re.findall(r"\d{6,25}", text)
        if direct:
            return max(direct, key=len)

        # 2) Handle grouped formats like "6222 0212 3456 7890" or "6222-0212-...".
        compact = re.sub(r"[\s\-_–—]+", "", text)
        grouped = re.findall(r"\d{6,25}", compact)
        if grouped:
            return max(grouped, key=len)

        # 3) Last resort: pure digits but must still be in valid range.
        digits = "".join(ch for ch in compact if ch.isdigit())
        if 6 <= len(digits) <= 25:
            return digits
        return ""

    def _capture_card_number_from_selection(self):
        copy_hotkeys = ("ctrl+c", "ctrl+insert", "ctrl+c")
        last_text = ""
        for idx, hotkey in enumerate(copy_hotkeys, 1):
            try:
                keyboard.send(hotkey)
            except Exception:
                pass

            time.sleep(0.10 + idx * 0.05)
            try:
                last_text = pyperclip.paste() or ""
            except Exception:
                last_text = ""

            card_number = self._extract_candidate_card_number(last_text)
            if card_number:
                return card_number, f"copy={hotkey}, attempt={idx}, clipboard_len={len(last_text)}"

        # One more delayed read to avoid WPS clipboard timing issues.
        time.sleep(0.18)
        try:
            last_text = pyperclip.paste() or ""
        except Exception:
            last_text = ""

        card_number = self._extract_candidate_card_number(last_text)
        if card_number:
            return card_number, f"copy=delayed-read, clipboard_len={len(last_text)}"

        sample = (last_text or "").replace("\r", " ").replace("\n", " ")[:80]
        return "", f"clipboard_no_valid_digits(len={len(last_text)}, sample={sample!r})"

    def _mark_click_event(self) -> bool:
        now = time.time()
        if now - self._last_click_ts < 0.35:
            return False
        self._last_click_ts = now
        return True

    def _trigger_query_from_current_selection(self, cursor_pos=None, source="unknown"):
        if not self.is_listening:
            self._debug_log_listener(f"[{source}] 跳过：监听开关关闭")
            return
        hwnd, title, class_name, exe_name = self._get_foreground_window_info()
        if not self._is_wps_window_info(title, class_name, exe_name):
            self._debug_log_listener(
                f"[{source}] 跳过：前台不是WPS表格 | exe={exe_name or '-'} | class={class_name or '-'} | title={(title or '-')[:90]}"
            )
            return
        if not self._mark_click_event():
            self._debug_log_listener(f"[{source}] 跳过：点击去重(350ms)")
            return
        self._debug_log_listener(f"[{source}] 点击捕获，准备读取单元格")

        def _worker():
            # Wait a short time to let WPS finish single-click selection.
            time.sleep(0.22)
            card_number, capture_info = self._capture_card_number_from_selection()
            if not card_number:
                self._debug_log_listener(f"[{source}] 捕获失败：{capture_info}")
                return

            if cursor_pos is None:
                self._debug_log_listener(
                    f"[{source}] 捕获成功：长度={len(card_number)}，触发查询，{capture_info}"
                )
                self.do_manual_query(card_number)
                return

            self._debug_log_listener(
                f"[{source}] 捕获成功：长度={len(card_number)}，触发查询+弹窗定位，{capture_info}"
            )
            record = perform_full_query(card_number, self.signal_sender)
            self.signal_sender.show_popup_signal.emit(card_number, record, cursor_pos)

        threading.Thread(target=_worker, daemon=True).start()

    def _start_mouse_polling(self):
        if self._mouse_poll_timer.isActive():
            return
        self._mouse_button_down = False
        self._mouse_poll_timer.start()
        self._debug_log_listener("鼠标轮询监听已启动")

    def _stop_mouse_polling(self):
        if self._mouse_poll_timer.isActive():
            self._mouse_poll_timer.stop()
            self._debug_log_listener("鼠标轮询监听已停止")
        self._mouse_button_down = False

    def _poll_mouse_left_click(self):
        if not self.is_listening:
            self._mouse_button_down = False
            return
        if not self._is_wps_spreadsheet_foreground():
            self._mouse_button_down = False
            return

        try:
            is_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        except Exception:
            return

        if is_down and not self._mouse_button_down:
            self._debug_log_listener("[poll] 检测到左键按下")
            self._trigger_query_from_current_selection(cursor_pos=None, source="poll")

        self._mouse_button_down = is_down

    def _start_mouse_listener(self):
        if self._mouse_listener and self._mouse_listener.running:
            return
        try:
            from pynput import mouse as pynput_mouse

            def on_click(x, y, button, pressed):
                if not pressed or button != pynput_mouse.Button.left:
                    return
                qpt = QPoint(int(x), int(y))
                self._trigger_query_from_current_selection(cursor_pos=qpt, source="hook")

            self._mouse_listener = pynput_mouse.Listener(on_click=on_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
            self._listener_error_notified = False
            self._debug_log_listener("pynput 鼠标钩子监听已启动")
        except Exception as exc:
            self._debug_log_listener(f"pynput 鼠标钩子启动失败：{exc}")
            print(f"Mouse listener init failed: {exc}")
            if hasattr(self, "tray_icon") and not self._listener_error_notified:
                self._listener_error_notified = True
                self.tray_icon.showMessage(
                    "监听启动失败",
                    f"鼠标监听初始化失败：{exc}",
                    QSystemTrayIcon.MessageIcon.Warning,
                    4500,
                )

    def _stop_mouse_listener(self):
        if self._mouse_listener and self._mouse_listener.running:
            try:
                self._mouse_listener.stop()
                self._debug_log_listener("pynput 鼠标钩子监听已停止")
            except Exception:
                pass
        self._mouse_listener = None

    def _get_foreground_process_name(self, hwnd) -> str:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            process_id = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if not process_id.value:
                return ""

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
            if not h_process:
                return ""

            try:
                size = wintypes.DWORD(1024)
                buffer = ctypes.create_unicode_buffer(1024)
                ok = kernel32.QueryFullProcessImageNameW(h_process, 0, buffer, ctypes.byref(size))
                if not ok:
                    return ""
                return os.path.basename(buffer.value or "").lower()
            finally:
                kernel32.CloseHandle(h_process)
        except Exception:
            return ""

    def _get_foreground_window_info(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return 0, "", "", ""

            title_buf = ctypes.create_unicode_buffer(512)
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 512)
            user32.GetClassNameW(hwnd, class_buf, 256)

            title = (title_buf.value or "").lower()
            class_name = (class_buf.value or "").lower()
            exe_name = self._get_foreground_process_name(hwnd)
            return hwnd, title, class_name, exe_name
        except Exception:
            return 0, "", "", ""

    def _is_wps_window_info(self, title: str, class_name: str, exe_name: str) -> bool:
        if not title and not class_name and not exe_name:
            return False

        title = (title or "").lower()
        class_name = (class_name or "").lower()
        exe_name = (exe_name or "").lower()

        spreadsheet_title_tokens = (".et", ".xls", ".xlsx", "表格", "工作簿", "sheet", "excel")
        non_sheet_tokens = ("文字", "writer", ".doc", ".docx", "word", "演示", "presentation", ".ppt", ".pptx")
        class_tokens = ("etmain", "ketmain", "wpset", "etframe", "etwnd", "xlmain", "excel")

        if exe_name == "et.exe":
            return True

        class_hit = any(token in class_name for token in class_tokens)
        if class_hit and exe_name in {"et.exe", "wps.exe"}:
            return True

        if class_hit and ("wps" in title or ".et" in title or "表格" in title):
            return True

        if exe_name == "wps.exe":
            if any(token in title for token in non_sheet_tokens):
                return False
            if any(token in title for token in spreadsheet_title_tokens):
                return True
            # permissive fallback for environments where title/class are non-standard.
            if "wps" in title and not any(token in title for token in non_sheet_tokens):
                return True

        if any(token in title for token in spreadsheet_title_tokens) and ("wps" in title or "et" in title):
            return True

        return False

    def _is_wps_spreadsheet_foreground(self) -> bool:
        _hwnd, title, class_name, exe_name = self._get_foreground_window_info()
        return self._is_wps_window_info(title, class_name, exe_name)

    def display_popup(self, card_number, record, cursor_pos=None):
        self.popup.show_result(card_number, record, cursor_pos)
        if self.panel_registry is not None:
            self.panel_registry.refresh_visible_panels()


if __name__ == "__main__":
    app = BinApp(sys.argv)
    sys.exit(app.exec())
