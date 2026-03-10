from __future__ import annotations

import sys

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ResultPopup(QWidget):
    """Bottom-right toast notification for BIN lookup status/result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.dismiss)

        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(260)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(180)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedSize(460, 260)
        self.setStyleSheet(
            """
            QWidget#card {
                background-color: #1f1f24;
                border: 1px solid #3d4350;
                border-radius: 12px;
            }
            QLabel {
                color: #f5f5f5;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
            }
            QLabel#title {
                font-size: 16px;
                font-weight: bold;
                color: #72c8ff;
            }
            QLabel#hint {
                color: #ffd47f;
                font-size: 12px;
            }
            QPushButton#close {
                background-color: transparent;
                border: 1px solid #596171;
                color: #cfd6e5;
                border-radius: 8px;
                font-size: 11px;
                font-weight: bold;
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
                padding: 0px;
            }
            QPushButton#close:hover {
                border-color: #ffffff;
                color: #ffffff;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self.card = QWidget(self)
        self.card.setObjectName("card")
        root.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.lbl_title = QLabel("BIN 查询结果")
        self.lbl_title.setObjectName("title")
        self.lbl_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.btn_close = QPushButton("X")
        self.btn_close.setObjectName("close")
        self.btn_close.clicked.connect(self.dismiss)

        self.lbl_card_no = QLabel("卡号: -")
        self.lbl_bank_name = QLabel("银行名称: -")
        self.lbl_card_type = QLabel("卡类型: -")
        self.lbl_card_length = QLabel("卡号位数: -")
        self.lbl_source = QLabel("来源: -")

        self.lbl_hint = QLabel("")
        self.lbl_hint.setObjectName("hint")
        self.lbl_hint.setWordWrap(True)

        for label in [
            self.lbl_card_no,
            self.lbl_bank_name,
            self.lbl_card_type,
            self.lbl_card_length,
            self.lbl_source,
        ]:
            label.setWordWrap(True)

        title_row = QHBoxLayout()
        title_row.addWidget(self.lbl_title)
        title_row.addStretch()
        title_row.addWidget(self.btn_close)

        layout.addLayout(title_row)
        layout.addWidget(self.lbl_card_no)
        layout.addWidget(self.lbl_bank_name)
        layout.addWidget(self.lbl_card_type)
        layout.addWidget(self.lbl_card_length)
        layout.addWidget(self.lbl_source)
        layout.addWidget(self.lbl_hint)

    def show_result(self, card_number, record, cursor_pos=None):
        # cursor_pos is ignored intentionally: notification is fixed bottom-right.
        record = record or {}
        self.lbl_card_no.setText(f"卡号: {card_number}")

        if record.get("_status") == "searching":
            self.lbl_title.setText("BIN 查询中")
            self.lbl_bank_name.setText("银行名称: 本地库未命中")
            self.lbl_card_type.setText("卡类型: -")
            self.lbl_card_length.setText("卡号位数: -")
            self.lbl_source.setText("来源: 网络查询")

            website_text = record.get("website_text") or ""
            if not website_text:
                urls = record.get("website_urls") or []
                website_text = "\n".join(str(u) for u in urls)
            self.lbl_hint.setText(f"正在以下网站查询:\n{website_text}")
            self.card.setStyleSheet(
                "background-color:#1f1f24; border:1px solid #f5a524; border-radius:12px;"
            )
        else:
            bank_name = record.get("bank_name") or "未查询到"
            card_type = record.get("card_type") or "-"
            card_length = record.get("card_length")
            source = record.get("source") or "-"

            self.lbl_title.setText("BIN 查询结果")
            self.lbl_bank_name.setText(f"银行名称: {bank_name}")
            self.lbl_card_type.setText(f"卡类型: {card_type}")
            self.lbl_card_length.setText(f"卡号位数: {card_length if card_length else '-'}")
            self.lbl_source.setText(f"来源: {source}")
            self.lbl_hint.setText("")

            if bank_name == "未查询到":
                self.card.setStyleSheet(
                    "background-color:#1f1f24; border:1px solid #ff6b6b; border-radius:12px;"
                )
            else:
                self.card.setStyleSheet(
                    "background-color:#1f1f24; border:1px solid #50b8ff; border-radius:12px;"
                )

        self._show_slide_up()

    def _target_position(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        margin = 16
        x = screen.right() - self.width() - margin
        y = screen.bottom() - self.height() - margin
        return x, y, screen

    def _show_slide_up(self):
        x, y, screen = self._target_position()
        start_y = screen.bottom() + 2

        self._slide_anim.stop()
        self._fade_anim.stop()

        self.setWindowOpacity(0.98)
        self.move(x, start_y)
        self.show()
        self.raise_()

        self._slide_anim.setStartValue(self.pos())
        self._slide_anim.setEndValue(QPoint(x, y))
        self._slide_anim.start()

        self._auto_close_timer.start(5000)

    def dismiss(self):
        self._auto_close_timer.stop()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)

        try:
            self._fade_anim.finished.disconnect()
        except Exception:
            pass

        def _hide_after_fade():
            self.hide()
            self.setWindowOpacity(1.0)

        self._fade_anim.finished.connect(_hide_after_fade)
        self._fade_anim.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    popup = ResultPopup()
    popup.show_result(
        "6222021234567890",
        {
            "bank_name": "中国工商银行",
            "card_type": "借记卡",
            "card_length": 19,
            "source": "LocalDB",
        },
    )
    sys.exit(app.exec())
