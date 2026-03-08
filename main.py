import sys
import ctypes
import crash_reporter
sys.excepthook = crash_reporter.upload_crash_log_to_bmob

# ── 单例保护：同一时刻只允许一个实例运行 ──────────────────────────────
_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "NJXiaohe_SingleInstance_2026")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    ctypes.windll.user32.MessageBoxW(
        None,
        "纪小盒 已经在运行中！\n\n请检查底部任务栏右侧的托盘图标（右键可打开面板）。",
        "纪小盒",
        0x40 | 0x1000  # MB_ICONINFORMATION | MB_SYSTEMMODAL
    )
    sys.exit(0)
# ──────────────────────────────────────────────────────────────────────

import threading
import time
import keyboard
import pyperclip
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget, QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton
from PyQt6.QtGui import QIcon, QPixmap, QImage, QPainter, QColor
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from ui_panel import MainPanel
from ui_popup import ResultPopup
from query_engine import perform_full_query, get_query_history
from settings_manager import load_settings, save_settings
from PyQt6.QtCore import pyqtSlot, QTimer
import requests

class GlobalSignalSender(QObject):
    # (card_number, record, cursor_pos_as_QPoint)
    show_popup_signal = pyqtSignal(str, object, object)
    
class HotkeyRecorder(QLineEdit):
    def __init__(self, current_hotkey, parent=None):
        super().__init__(current_hotkey, parent)
        self.setReadOnly(True)
        # Translates Qt keys to keyboard module strings
        self.key_map = {
            Qt.Key.Key_Control: 'ctrl',
            Qt.Key.Key_Alt: 'alt',
            Qt.Key.Key_Shift: 'shift',
            Qt.Key.Key_Meta: 'windows'
        }
        
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            return super().keyPressEvent(event)
            
        modifiers = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            modifiers.append('ctrl')
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            modifiers.append('alt')
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            modifiers.append('shift')
        if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            modifiers.append('windows')
            
        key_text = ""
        # Handle special key texts like ~
        if event.text():
            key_text = event.text().lower()
        else:
            # Fallback for keys that don't produce text
            from PyQt6.QtGui import QKeySequence
            key_text = QKeySequence(key).toString().lower()
            
        if not key_text:
            return
            
        if key_text == '`': # Handle tilde/backtick
            key_text = '~'
            
        parts = modifiers + [key_text]
        new_hotkey = "+".join(parts)
        self.setText(new_hotkey)
        
    
class SettingsDialog(QDialog):
    def __init__(self, current_hotkey, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置快捷键")
        self.setFixedSize(300, 120)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #FFFFFF; }
            QLabel { color: #FFFFFF; font-family: 'Microsoft YaHei'; }
            QLineEdit { background-color: #2D2D30; border: 1px solid #3E3E42; color: #FFFFFF; padding: 4px; }
            QPushButton { background-color: #007ACC; color: white; border: none; padding: 5px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #1C97EA; }
        """)
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("请直接在下方按键以设置新的全局快捷键:")
        layout.addWidget(lbl)
        
        self.input_hotkey = HotkeyRecorder(current_hotkey)
        self.input_hotkey.setPlaceholderText("点击这里，然后按下快捷组合键 (如 Ctrl+~)")
        layout.addWidget(self.input_hotkey)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
    def get_hotkey(self):
        return self.input_hotkey.text().strip()
    
class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修改密码")
        self.setFixedSize(300, 180)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #FFFFFF; }
            QLabel { color: #CCCCCC; font-family: 'Microsoft YaHei'; font-size: 12px; }
            QLineEdit { background-color: #2D2D30; border: 1px solid #3E3E42; color: #FFFFFF; padding: 6px; border-radius: 3px; }
            QPushButton { background-color: #007ACC; color: white; border: none; padding: 6px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1C97EA; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        self.input_old = QLineEdit()
        self.input_old.setPlaceholderText("旧密码")
        self.input_old.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input_old)

        self.input_new = QLineEdit()
        self.input_new.setPlaceholderText("新密码")
        self.input_new.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input_new)

        self.input_confirm = QLineEdit()
        self.input_confirm.setPlaceholderText("再次输入新密码")
        self.input_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input_confirm)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("确认修改")
        btn_save.clicked.connect(self._do_change)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _do_change(self):
        old = self.input_old.text().strip()
        new = self.input_new.text().strip()
        confirm = self.input_confirm.text().strip()
        # Only proceed if new passwords match and both fields filled
        if new and new == confirm and old:
            from bmob_client import change_password
            change_password(old, new)  # Silent -- no feedback on success or failure
        self.accept()  # Always close dialog without any message


class BinApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        
        self.settings = load_settings()
        
        # Ensure the SQLite database and tables exist before anything queries them
        from data_manager import init_db
        init_db()
        
        self.signal_sender = GlobalSignalSender()
        self.signal_sender.show_popup_signal.connect(self.display_popup)
        
        self.main_panel = MainPanel(self.signal_sender)
        self.popup = ResultPopup()
        
        self.is_listening = True    # True = monitoring mode enabled
        self._mouse_listener = None  # pynput listener ref
        
        # Show login dialog first (silent failure model)
        self._show_login_dialog()
        
        # Update main panel title to include the logged-in username
        from bmob_client import get_current_username
        uname = get_current_username() or "--"
        self.main_panel.setWindowTitle(f"纪小盒-银行BIN码  登录账户：{uname}")
        
        self.init_tray()
        self.restart_hotkey_listener()
     
    def _show_login_dialog(self):
        """Try auto-login from saved credentials. Show dialog only if not yet saved or auth fails."""
        from bmob_client import login, is_authorized
        
        saved_user = self.settings.get("username", "")
        saved_pass = self.settings.get("password", "")
        
        # Try auto-login if credentials already saved
        if saved_user and saved_pass:
            login(saved_user, saved_pass)
            if is_authorized():
                return  # Auto-login succeeded, skip dialog
        
        # Show login dialog
        dlg = QDialog()
        dlg.setWindowTitle("纪小盒 银行BIN码查询")
        dlg.setFixedSize(380, 280)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        dlg.setStyleSheet("""
            QDialog { background-color: #FFFFFF; }
            QLabel#lbl_field { 
                color: #333355; 
                font-family: 'Microsoft YaHei';
                font-size: 13px;
                font-weight: bold;
                min-width: 42px;
                max-width: 42px;
            }
            QLabel#lbl_title { 
                color: #007ACC; 
                font-family: 'Microsoft YaHei'; 
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#lbl_sub { 
                color: #888; 
                font-family: 'Microsoft YaHei'; 
                font-size: 11px;
            }
            QLineEdit { 
                background-color: #F7F8FC; 
                border: 1px solid #D0D3DC; 
                color: #1A1A2E; 
                padding: 8px 10px; 
                border-radius: 5px; 
                font-size: 13px; 
                font-family: 'Microsoft YaHei';
            }
            QLineEdit:focus { border: 1.5px solid #007ACC; background-color:#FFFFFF; }
            QPushButton#login_btn { 
                background-color: #007ACC; 
                color: white; 
                border: none; 
                padding: 10px; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 14px; 
                font-family: 'Microsoft YaHei';
            }
            QPushButton#login_btn:hover { background-color: #1C97EA; }
            QPushButton#login_btn:pressed { background-color: #005A9E; }
            QPushButton#toggle_btn { 
                background-color: transparent; 
                color: #AAAAAA; 
                border: none; 
                padding: 4px 6px; 
                font-size: 14px; 
            }
            QPushButton#toggle_btn:hover { color: #007ACC; }
        """)
        
        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 28, 30, 28)
        
        lbl_title = QLabel("纪小盒 银行BIN码查询")
        lbl_title.setObjectName("lbl_title")
        from PyQt6.QtGui import QFont
        layout.addWidget(lbl_title)
        
        lbl_sub = QLabel("请登录授权账号以继续使用")
        lbl_sub.setObjectName("lbl_sub")
        layout.addWidget(lbl_sub)
        
        lbl_error = QLabel("")
        lbl_error.setStyleSheet("color: red; font-size: 12px; font-weight: bold;")
        lbl_error.hide()
        layout.addWidget(lbl_error)
        
        layout.addSpacing(4)
        
        # Account row
        user_row = QHBoxLayout()
        lbl_u = QLabel("账号")
        lbl_u.setObjectName("lbl_field")
        input_user = QLineEdit()
        input_user.setPlaceholderText("请输入账号")
        if saved_user:
            input_user.setText(saved_user)
        user_row.addWidget(lbl_u)
        user_row.addWidget(input_user)
        layout.addLayout(user_row)
        
        # Password row with toggle visibility
        pass_row = QHBoxLayout()
        lbl_p = QLabel("密码")
        lbl_p.setObjectName("lbl_field")
        input_pass = QLineEdit()
        input_pass.setPlaceholderText("请输入密码")
        input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        if saved_pass:
            input_pass.setText(saved_pass)
        
        btn_toggle = QPushButton("👁")
        btn_toggle.setObjectName("toggle_btn")
        btn_toggle.setFixedWidth(34)
        btn_toggle.setCheckable(True)
        def toggle_visibility(checked):
            input_pass.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            btn_toggle.setText("🔒" if checked else "👁")
        btn_toggle.clicked.connect(toggle_visibility)
        
        pass_row.addWidget(lbl_p)
        pass_row.addWidget(input_pass)
        pass_row.addWidget(btn_toggle)
        layout.addLayout(pass_row)
        
        layout.addSpacing(4)
        
        btn_login = QPushButton("🔑  登 录")
        btn_login.setObjectName("login_btn")
        layout.addWidget(btn_login)

        def do_login():
            lbl_error.hide()
            uname = input_user.text().strip()
            upass = input_pass.text().strip()
            
            if not uname or not upass:
                lbl_error.setText("账号和密码不能为空！")
                lbl_error.show()
                return
                
            ok = login(uname, upass)
            if ok:
                # Save credentials only on success
                self.settings["username"] = uname
                self.settings["password"] = upass
                
                # Check first run
                is_first_run = not self.settings.get("first_run_done", False)
                if is_first_run:
                    self.settings["first_run_done"] = True
                    # Schedule show main panel after init
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(500, self.show_main_panel)
                    
                save_settings(self.settings)
                dlg.accept()
            else:
                lbl_error.setText("登录失败：账号或密码错误！")
                lbl_error.show()
            
        btn_login.clicked.connect(do_login)
        input_pass.returnPressed.connect(do_login)
        
        dlg.exec()
        
        # If dialog was closed without successful login, exit app
        if not is_authorized():
            import sys
            sys.exit(0)
        
    def init_tray(self):
        # Create a simple icon programmatically: white square, rounded corners, blue text '纪'
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        
        # Draw white square with rounded corners
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(0, 0, 32, 32, 8, 8)
        
        # Draw blue '纪' text
        from PyQt6.QtGui import QFont
        painter.setPen(QColor("#007ACC"))
        font = QFont("Microsoft YaHei", 18, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "纪")
        painter.end()
        
        self.tray_icon = QSystemTrayIcon(QIcon(pixmap), self)
        
        # Menu - styled for bigger, cleaner look
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet("""
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
            QMenu::item:selected {
                background-color: #E8F0FE;
                color: #007ACC;
            }
            QMenu::item:disabled {
                color: #999999;
                font-style: italic;
            }
            QMenu::separator {
                height: 1px;
                background: #E0E3EE;
                margin: 4px 10px;
            }
        """)
        
        # 1. Top most: Login Account
        from bmob_client import get_current_username
        self.action_user = self.tray_menu.addAction(f"当前账号: {get_current_username()}")
        self.action_user.setEnabled(False)  # Just info, not clickable
        
        self.tray_menu.addSeparator()
        
        # 2. Query websites submenu
        self.api_menu = QMenu("查询网址", self.tray_menu)
        act_api1 = self.api_menu.addAction("1. 支付宝验证接口 (ccdcapi.alipay.com)")
        act_api1.setEnabled(False)
        act_api2 = self.api_menu.addAction("2. 云端兜底接口 (cardbin.cn)")
        act_api2.setEnabled(False)
        self.tray_menu.addMenu(self.api_menu)
        
        self.tray_menu.addSeparator()
        
        # Recent searches top items
        self.recent_menu = QMenu("历史搜索记录", self.tray_menu)
        self.tray_menu.addMenu(self.recent_menu)
        self.tray_menu.aboutToShow.connect(self.update_recent_menu)
        
        self.tray_menu.addSeparator()
        
        self.action_show = self.tray_menu.addAction("📊 打开控制面板")
        self.action_show.triggered.connect(self.show_main_panel)
        
        hotkey = self.settings.get("hotkey", "f6").upper()
        self.action_settings = self.tray_menu.addAction(f"⌨ 设置  [当前快捷键: {hotkey}]")
        self.action_settings.triggered.connect(self.open_settings)
        
        self.action_change_pw = self.tray_menu.addAction("修改密码")
        self.action_change_pw.triggered.connect(self.open_change_password)
        
        self.action_toggle = self.tray_menu.addAction("监听开关: 已开启")
        self.action_toggle.triggered.connect(self.toggle_listener)
        
        self.tray_menu.addSeparator()
        
        # Lowest: About / Version info
        self.about_menu = QMenu("关于 纪小盒 V1.6", self.tray_menu)
        self.act_curr_ver = self.about_menu.addAction("当前版本号: V1.6")
        self.act_curr_ver.setEnabled(False)
        self.act_download = self.about_menu.addAction("检查更新中...")
        self.act_download.setEnabled(False)
        self.tray_menu.addMenu(self.about_menu)
        
        self.action_time = self.tray_menu.addAction("更新时间: 2026-03-09")
        self.action_time.setEnabled(False)
        
        self.tray_menu.addSeparator()
        
        self.action_quit = self.tray_menu.addAction("退出程序")
        self.action_quit.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.setToolTip("纪小盒 银行BIN码查询 V1.6")
        
        # Double click to open panel
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        self.tray_icon.show()
        
        # Start update check threaded
        threading.Thread(target=self.check_github_update, daemon=True).start()
        
    def check_github_update(self):
        """Check GitHub for new releases. Hardcoded user/repo can be updated later."""
        current_version = "v1.6"
        github_user = "mountopjh"
        github_repo = "jixiaohe2026"
        api_url = f"https://api.github.com/repos/{github_user}/{github_repo}/releases/latest"
        
        try:
            import requests
            # Short timeout to not hang
            resp = requests.get(api_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest_version = data.get("tag_name", "").lower()
                if latest_version and latest_version.strip('v') > current_version.strip('v'):
                    release_url = data.get("html_url", "")
                    
                    # Try to find an .exe asset for direct download
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".exe"):
                            release_url = asset.get("browser_download_url", release_url)
                            break
                    
                    # Need to update UI in main thread
                    from PyQt6.QtCore import QMetaObject, Q_ARG, Qt
                    QMetaObject.invokeMethod(self, "on_update_found",
                                          Qt.ConnectionType.QueuedConnection,
                                          Q_ARG(str, latest_version),
                                          Q_ARG(str, release_url))
        except Exception as e:
            print(f"Github update check failed: {e}")
            pass

    @pyqtSlot(str, str)
    def on_update_found(self, latest_version, release_url):
        # Change About menu to red
        self.about_menu.setTitle("🔴 关于 纪小盒 (有新版本)")
        # Qt doesn't directly support coloring individual QMenu titles easily without 
        # completely custom painting in standard stylesheets, but we can set an icon or 
        # change the menu's own text. For better visibility we just used the emoji.
        
        # Update download button
        self.act_download.setText("🚀 点击下载更新")
        self.act_download.setEnabled(True)
        
        def open_url():
            import webbrowser
            webbrowser.open(release_url)
            
        self.act_download.triggered.connect(open_url)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_panel()
            
    def show_main_panel(self):
        self.main_panel.load_history()
        self.main_panel.show()
        self.main_panel.activateWindow()
        
    def toggle_listener(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.action_toggle.setText("开关: 已开启")
        else:
            self.action_toggle.setText("开关: 已关闭")
            
    def quit_app(self):
        self.tray_icon.hide()
        self.quit()
        
    def update_recent_menu(self):
        self.recent_menu.clear()
        # Only show successfully matched results (success_only=True)
        history = get_query_history(success_only=True)[:20]
        if not history:
            self.recent_menu.addAction("暂无记录").setEnabled(False)
            return
            
        for r in history:
            card_type = r.get('card_type', '') or ''
            bank = r.get('bank_name', '未知') or '未知'
            card_no = r.get('card_no', '') or ''
            source = r.get('source', '') or ''
            type_str = f" [{card_type}]" if card_type else ""
            text = f"{card_no} | {bank}{type_str} ({source})"
            action = self.recent_menu.addAction(text)
            action.triggered.connect(lambda checked, num=card_no: self.do_manual_query(num))
            
    def do_manual_query(self, card_number):
        record = perform_full_query(card_number)
        self.display_popup(card_number, record)
            
    def open_settings(self):
        # Default changed to 'f6'
        dlg = SettingsDialog(self.settings.get("hotkey", "f6"))
        if dlg.exec():
            new_hotkey = dlg.get_hotkey()
            self.settings["hotkey"] = new_hotkey
            save_settings(self.settings)
            self.restart_hotkey_listener()
            
    def open_change_password(self):
        dlg = ChangePasswordDialog()
        dlg.exec()
        
    def get_current_hotkey(self):
        return self.settings.get("hotkey", "f6")
            
    def restart_hotkey_listener(self):
        """Bind the monitor-toggle hotkey and the ESC dismiss key."""
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook_all()
        except:
            pass
            
        def hotkey_loop():
            target_hotkey = self.get_current_hotkey()
            try:
                keyboard.add_hotkey(target_hotkey, self._toggle_monitoring)
            except Exception as e:
                print(f"Failed to bind hotkey {target_hotkey}: {e}")
            
            # ESC dismisses popup from anywhere
            def on_esc(e):
                if e.event_type == keyboard.KEY_DOWN and e.name == 'esc':
                    if self.popup.isVisible():
                        self.popup.dismiss()
            keyboard.hook(on_esc)
            keyboard.wait()

        t = threading.Thread(target=hotkey_loop, daemon=True)
        t.start()

    def _toggle_monitoring(self):
        """Toggle monitoring mode on/off.  Update tray icon label."""
        self.is_listening = not self.is_listening
        label = "监听开关: 已开启" if self.is_listening else "监听开关: 已关闭"
        self.action_toggle.setText(label)

        if self.is_listening:
            self._start_mouse_listener()
        else:
            self._stop_mouse_listener()
            # Hide popup when turning off monitoring
            if self.popup.isVisible():
                self.popup.dismiss()

    def _start_mouse_listener(self):
        """Start pynput mouse listener to watch left-click events."""
        if self._mouse_listener and self._mouse_listener.running:
            return  # Already running
        try:
            from pynput import mouse as pynput_mouse
            from PyQt6.QtCore import QPoint
            def on_click(x, y, button, pressed):
                if not pressed:
                    return  # Only act on press, not release
                if button != pynput_mouse.Button.left:
                    return
                if not self.is_listening:
                    return
                # Capture clipboard content AFTER the click is processed
                # We wait briefly so Excel can update the selected cell text
                import time
                time.sleep(0.15)
                try:
                    import pyperclip
                    text = pyperclip.paste()
                    # Extract digits from whatever was already in clipboard
                    # (cell click in Excel often does NOT auto-copy, so we try
                    # a silent keyboard approach: read the cell directly via
                    # pressing F2+Esc trick to keep selection, then copy with
                    # Ctrl+C — but we suppress the animation by immediately
                    # pressing Esc to cancel the cell copy border)
                    keyboard.send('ctrl+c')
                    time.sleep(0.08)
                    new_text = pyperclip.paste()
                    # Cancel copy border in Excel: send Esc to remove marching ants
                    keyboard.send('esc')
                    
                    card_number = "".join(c for c in new_text if c.isdigit())
                    if card_number:
                        from PyQt6.QtCore import QPoint
                        qpt = QPoint(int(x), int(y))
                        record = perform_full_query(card_number)
                        self.signal_sender.show_popup_signal.emit(card_number, record, qpt)
                except Exception:
                    pass

            self._mouse_listener = pynput_mouse.Listener(on_click=on_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
        except ImportError:
            print("pynput not available; falling back to hotkey-only mode")

    def _stop_mouse_listener(self):
        """Stop the pynput mouse listener."""
        if self._mouse_listener and self._mouse_listener.running:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
        self._mouse_listener = None

    def display_popup(self, card_number, record, cursor_pos=None):
        from PyQt6.QtCore import QPoint
        if isinstance(cursor_pos, QPoint):
            from PyQt6.QtGui import QCursor
            self.popup.show_result(card_number, record, cursor_pos)
        else:
            self.popup.show_result(card_number, record)
        if self.main_panel.isVisible():
            self.main_panel.load_history()

if __name__ == '__main__':
    app = BinApp(sys.argv)
    sys.exit(app.exec())
