import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, QPoint
from PyQt6.QtGui import QFont, QCursor, QColor
import ctypes
from ctypes.wintypes import HWND

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
        
        self.init_ui()
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")

    def init_ui(self):
        self.setFixedSize(300, 160)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Main container with rounded corners and shadow simulation
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
        
        # Title
        self.lbl_title = QLabel("BIN码查询结果")
        self.lbl_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #4DB8FF;")
        
        # Content labels
        self.lbl_card_no = QLabel("卡号: ")
        self.lbl_card_no.setFont(QFont("Consolas", 10))
        
        self.lbl_bank_name = QLabel("银行: ")
        self.lbl_bank_name.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        
        self.lbl_card_type = QLabel("类型: ")
        self.lbl_card_type.setFont(QFont("Microsoft YaHei", 10))
        
        self.lbl_source = QLabel("来源: ")
        self.lbl_source.setFont(QFont("Microsoft YaHei", 8))
        self.lbl_source.setStyleSheet("color: #AAAAAA;")
        self.lbl_source.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        v_layout.addWidget(self.lbl_title)
        v_layout.addWidget(self.lbl_card_no)
        v_layout.addWidget(self.lbl_bank_name)
        v_layout.addWidget(self.lbl_card_type)
        v_layout.addWidget(self.lbl_source)
        
        layout.addWidget(self.container)
        self.setLayout(layout)
        
    def show_result(self, card_number, record):
        """Show the popup with animation"""
        self.lbl_card_no.setText(f"卡号: {card_number}")
        if record:
            self.lbl_bank_name.setText(f"银行: {record.get('bank_name', '未知')}")
            self.lbl_card_type.setText(f"类型: {record.get('card_type', '未知')}")
            self.lbl_source.setText(f"来源: {record.get('source', '网络查询')}")
            self.container.setStyleSheet("""
                #container {
                    background-color: #2D2D30;
                    border-radius: 12px;
                    border: 1px solid #4DB8FF;
                }
                QLabel { color: #FFFFFF; }
            """)
        else:
            self.lbl_bank_name.setText("未查找到对应的归属地信息")
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
            
        # Position near cursor
        self.position_near_cursor()
        self.setWindowOpacity(0.0)
        self.show()
        
        # Absolute Topmost via ctypes (fixes PyQt level bugs with other topmost windows)
        hwnd = int(self.winId())
        ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        
        # Fade in
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(250)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(0.95)
        self.opacity_anim.start()
        
    def position_near_cursor(self):
        # Get mouse position
        cursor_pos = QCursor.pos()
        # Offset slightly so it doesn't block the cursor completely
        x = cursor_pos.x() + 20
        y = cursor_pos.y() + 20
        
        # Adjust if off-screen (basic check)
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        if x + self.width() > screen.width():
            x = cursor_pos.x() - self.width() - 10
        if y + self.height() > screen.height():
            y = cursor_pos.y() - self.height() - 10
            
        self.move(x, y)
        
    def fade_out(self):
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.finished.connect(self.hide)
        self.opacity_anim.start()
        
    def mousePressEvent(self, event):
        # Click to dismiss
        self.fade_out()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.fade_out()
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
