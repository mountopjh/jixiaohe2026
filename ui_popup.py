from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget


class ResultPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(360)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        frame = QFrame(self)
        frame.setObjectName("frame")
        frame.setStyleSheet(
            """
            QFrame#frame {
                background: #ffffff;
                border: 1px solid #d5dae6;
                border-radius: 8px;
            }
            QLabel { color: #1a1a2e; font-family: 'Microsoft YaHei'; font-size: 13px; }
            QLabel#title { color: #007acc; font-size: 15px; font-weight: bold; }
            QLabel#key { color: #60646f; }
            QLabel#value { color: #1a1a2e; font-weight: bold; }
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        self._layout = QGridLayout(frame)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(7)

    def show_result(self, card_number: str, record, cursor_pos: QPoint | None = None) -> None:
        self._clear()
        data = record if isinstance(record, dict) else {}

        if data.get("_status") == "searching":
            self._add_title("正在查询")
            self._add_row(1, "卡号", card_number)
            self._add_row(2, "来源", data.get("website_text", "网络查询"))
            timeout_ms = 1800
        else:
            self._add_title("查询结果")
            self._add_row(1, "卡号", card_number)
            self._add_row(2, "BIN", data.get("bin_code", "-"))
            self._add_row(3, "银行", data.get("bank_name", "未查询到"))
            self._add_row(4, "卡类型", data.get("card_type", "-"))
            self._add_row(5, "长度", str(data.get("card_length", "-") or "-"))
            self._add_row(6, "来源", data.get("source", "-"))
            timeout_ms = 5200

        self.adjustSize()
        self._move_near_cursor(cursor_pos)
        self.show()
        self.raise_()
        self._timer.start(timeout_ms)

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()

    def _add_title(self, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("title")
        self._layout.addWidget(label, 0, 0, 1, 2)

    def _add_row(self, row: int, key: str, value: str) -> None:
        key_label = QLabel(key)
        key_label.setObjectName("key")
        value_label = QLabel(str(value or "-"))
        value_label.setObjectName("value")
        value_label.setWordWrap(True)
        self._layout.addWidget(key_label, row, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(value_label, row, 1)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _move_near_cursor(self, cursor_pos: QPoint | None) -> None:
        screen = self.screen()
        rect = screen.availableGeometry() if screen is not None else None
        pos = cursor_pos or self.cursor().pos()
        x = pos.x() + 16
        y = pos.y() + 16
        if rect is not None:
            x = min(max(rect.left(), x), rect.right() - self.width())
            y = min(max(rect.top(), y), rect.bottom() - self.height())
        self.move(x, y)
