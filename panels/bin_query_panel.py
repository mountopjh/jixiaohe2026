from __future__ import annotations

import threading

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from panels.base import PanelModule
from query_engine import get_query_history, perform_full_query


class BinQueryPanel(PanelModule):
    panel_id = "bin_query"
    panel_name = "BIN 查询"

    def __init__(self, signal_sender) -> None:
        super().__init__()
        self._signal_sender = signal_sender
        self._input: QLineEdit | None = None
        self._table: QTableWidget | None = None
        self._status: QLabel | None = None

    def create_widget(self) -> QWidget:
        widget = QWidget()
        widget.setWindowTitle("BankBin")
        widget.resize(760, 460)
        widget.setStyleSheet(
            """
            QWidget { background: #ffffff; color: #1a1a2e; font-family: 'Microsoft YaHei'; }
            QLineEdit {
                border: 1px solid #d0d3dc;
                border-radius: 5px;
                padding: 8px 10px;
                background: #fbfcff;
                font-size: 13px;
            }
            QPushButton {
                background: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1c97ea; }
            QTableWidget {
                border: 1px solid #dfe3ec;
                gridline-color: #eef0f5;
                selection-background-color: #e8f0fe;
                selection-color: #1a1a2e;
            }
            QHeaderView::section {
                background: #f5f7fb;
                color: #1a1a2e;
                border: none;
                border-bottom: 1px solid #dfe3ec;
                padding: 7px;
                font-weight: bold;
            }
            QLabel#title { color: #007acc; font-size: 16px; font-weight: bold; }
            QLabel#status { color: #60646f; font-size: 12px; }
            """
        )

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("BankBin")
        title.setObjectName("title")
        layout.addWidget(title)

        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入银行卡号或 BIN")
        self._input.returnPressed.connect(self._query_current)
        btn_query = QPushButton("查询")
        btn_query.clicked.connect(self._query_current)
        row.addWidget(self._input, 1)
        row.addWidget(btn_query)
        layout.addLayout(row)

        self._status = QLabel("就绪")
        self._status.setObjectName("status")
        layout.addWidget(self._status)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["卡号", "BIN", "银行", "卡类型", "长度", "来源"])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        self.refresh()
        return widget

    def refresh(self) -> None:
        if self._table is None:
            return

        history = get_query_history(success_only=False)[:100]
        self._table.setRowCount(len(history))
        for row_idx, row in enumerate(history):
            values = [
                row.get("card_no", ""),
                row.get("bin_code", ""),
                row.get("bank_name", ""),
                row.get("card_type", ""),
                str(row.get("card_length", "") or ""),
                row.get("source", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()

    def _query_current(self) -> None:
        if self._input is None:
            return
        card_number = "".join(ch for ch in self._input.text() if ch.isdigit())
        if not card_number:
            if self._status is not None:
                self._status.setText("请输入有效数字")
            return

        if self._status is not None:
            self._status.setText("查询中...")

        def worker() -> None:
            record = perform_full_query(card_number, self._signal_sender)
            self._signal_sender.show_popup_signal.emit(card_number, record, None)

        threading.Thread(target=worker, daemon=True).start()
