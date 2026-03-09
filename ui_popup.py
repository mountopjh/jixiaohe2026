import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint
from PyQt6.QtGui import QFont, QCursor
import ctypes

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

class ResultPopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._already_shown = False   # tracks if popup is currently on screen
        self.init_ui()
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        from PyQt6.QtCore import QTimer
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.dismiss)

    def init_ui(self):
        self.setFixedSize(300, 160)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Main container with rounded corners
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            #container {
                background-color: #2D2D30;
                border-radius: 12px;
                border: 1px solid #3E3E42;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)
        
        v_layout = QVBoxLayout(self.container)
        v_layout.setContentsMargins(15, 15, 15, 15)
        v_layout.setSpacing(8)
        
        # Title & Close Button Row
        title_layout = QHBoxLayout()
        self.lbl_title = QLabel("BIN码查询结果")
        self.lbl_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #4DB8FF;")
        
        from PyQt6.QtWidgets import QPushButton
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #FF5C5C;
            }
        """)
        self.btn_close.clicked.connect(self.dismiss)
        
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.btn_close)
        
        # Content labels
        self.lbl_card_no = QLabel("卡号: ")
        self.lbl_card_no.setFont(QFont("Consolas", 10))
        self.lbl_card_no.setWordWrap(True)
        
        self.lbl_bank_name = QLabel("银行: ")
        self.lbl_bank_name.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.lbl_bank_name.setWordWrap(True)
        
        self.lbl_card_type = QLabel("类型: ")
        self.lbl_card_type.setFont(QFont("Microsoft YaHei", 10))
        
        self.lbl_source = QLabel("来源: ")
        self.lbl_source.setFont(QFont("Microsoft YaHei", 8))
        self.lbl_source.setStyleSheet("color: #AAAAAA;")
        self.lbl_source.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        v_layout.addLayout(title_layout)
        v_layout.addWidget(self.lbl_card_no)
        v_layout.addWidget(self.lbl_bank_name)
        v_layout.addWidget(self.lbl_card_type)
        v_layout.addWidget(self.lbl_source)
        
        layout.addWidget(self.container)
        self.setLayout(layout)
        
    def show_result(self, card_number, record, cursor_pos=None):
        """Update content and move near cursor without flicker.
        If already visible, just update content + move.  Do NOT fade out then back in.
        """
        # Restart the 10-second auto-close timer every time we show/update the popup
        self.auto_close_timer.start(10000)
        
        # Update content
        self.lbl_card_no.setText(f"卡号: {card_number}")
        
        if record and record.get('_status') == 'searching':
            # This is the new intermediary state where network query is ongoing
            website_hint = "支付宝 或 Cardbin.cn"
            self.lbl_bank_name.setText(f"正在 {website_hint} 深度查询...\n请稍后在程序面板中查看最终结果。")
            self.lbl_card_type.setText("")
            self.lbl_card_type.hide()
            self.lbl_source.setText("")
            self.container.setStyleSheet("""
                #container {
                    background-color: #2D2D30;
                    border-radius: 12px;
                    border: 1px solid #FFA500;
                }
                QLabel { color: #FFFFFF; }
            """)
        elif record and record.get('bank_name') and record.get('bank_name') != '未知' and record.get('bank_name') != '未匹配到结果':
            # Valid local database hit
            self.lbl_bank_name.setText(f"银行: {record.get('bank_name', '未知')}")
            self.lbl_card_type.show()
            self.lbl_card_type.setText(f"类型: {record.get('card_type', '未知')}")
            # Hide source for final results to render cleaner
            self.lbl_source.setText("")
            self.container.setStyleSheet("""
                #container {
                    background-color: #2D2D30;
                    border-radius: 12px;
                    border: 1px solid #4DB8FF;
                }
                QLabel { color: #FFFFFF; }
            """)
        else:
            # Complete failure (very rare now since we do fallback background search, but just in case)
            self.lbl_bank_name.setText("未查找到对应的归属地信息")
            self.lbl_card_type.show()
            self.lbl_card_type.setText("类型: 未知")
            self.lbl_source.setText("")
            self.container.setStyleSheet("""
                #container {
                    background-color: #2D2D30;
                    border-radius: 12px;
                    border: 1px solid #FF5C5C;
                }
                QLabel { color: #FFFFFF; }
            """)

        # Move to near the click position
        self.position_near_cursor(cursor_pos)
        
        if self._already_shown:
            # Already visible — just move, no animation needed
            self._force_topmost()
            return

        # First time showing: fade in
        self._already_shown = True
        self.setWindowOpacity(0.0)
        self.show()
        self._force_topmost()
        
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(0.95)
        self.opacity_anim.start()

    def _force_topmost(self):
        """Use ctypes to make this window absolutely topmost (even above other topmost windows)."""
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
        except Exception:
            pass

    def position_near_cursor(self, cursor_pos=None):
        if cursor_pos is None:
            cursor_pos = QCursor.pos()
        x = cursor_pos.x() + 20
        y = cursor_pos.y() + 20
        
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        if x + self.width() > screen.width():
            x = cursor_pos.x() - self.width() - 10
        if y + self.height() > screen.height():
            y = cursor_pos.y() - self.height() - 10
        self.move(x, y)
    
    def dismiss(self):
        """Only way to dismiss the popup: ESC key, X button, or 10s timer."""
        self.auto_close_timer.stop()
        self._already_shown = False
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.0)
        # Use a safe disconnect pattern to avoid stale connections
        try:
            self.opacity_anim.finished.disconnect()
        except Exception:
            pass
        self.opacity_anim.finished.connect(self.hide)
        self.opacity_anim.start()

    def mousePressEvent(self, event):
        # Intentionally do NOTHING on click — popup should NOT be dismissed by clicking
        pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
        super().keyPressEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = ResultPopup()
    w.show_result("6222021234567890", {
        "bank_name": "中国工商银行",
        "card_type": "借记卡",
        "source": "LocalDB"
    })
    sys.exit(app.exec())
