from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data_manager import import_excel_to_db
from query_engine import clear_all_history, clear_failed_history, get_query_history, perform_full_query

logger = logging.getLogger(__name__)


class MainPanel(QWidget):
    def __init__(self, signal_sender=None, parent=None):
        super().__init__(parent)
        self.signal_sender = signal_sender
        self.setWindowTitle("纪小盒银行 BIN 查询")
        self.setMinimumSize(980, 560)

        self.setStyleSheet(
            """
            QWidget {
                background-color: #f5f6fa;
                color: #1a1a2e;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #dde1ec;
                border-radius: 6px;
                gridline-color: #eef0f8;
                selection-background-color: #d0e8ff;
                selection-color: #1a1a2e;
            }
            QHeaderView::section {
                background-color: #eef0f8;
                padding: 7px 5px;
                border: none;
                border-right: 1px solid #dde1ec;
                border-bottom: 1px solid #dde1ec;
                font-weight: bold;
                color: #333355;
                font-size: 13px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #c8cbda;
                border-radius: 6px;
                padding: 6px 14px;
                color: #1a1a2e;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #eef0f8;
                border-color: #007acc;
                color: #007acc;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #c8cbda;
                border-radius: 5px;
                padding: 7px 10px;
                color: #1a1a2e;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #007acc;
            }
            """
        )

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        header.addStretch()

        btn_refresh = QPushButton("刷新查询历史")
        btn_refresh.clicked.connect(self.refresh_history)

        btn_clear = QPushButton("清除查询记录")
        btn_clear.clicked.connect(self.clear_history)

        btn_import = QPushButton("导入 BIN 码表(.xlsx)")
        btn_import.clicked.connect(self.import_bin_db)

        btn_export = QPushButton("导出 BIN 码表模板(.xlsx)")
        btn_export.clicked.connect(self.export_bin_db)

        header.addWidget(btn_refresh)
        header.addWidget(btn_clear)
        header.addWidget(btn_import)
        header.addWidget(btn_export)
        layout.addLayout(header)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入卡号后点击查询")

        btn_search = QPushButton("查询")
        btn_search.clicked.connect(self.manual_search)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["查询时间", "卡号", "BIN码", "银行名称", "卡类型", "卡号位数", "来源"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)
        self.load_history()

    def load_history(self):
        self.table.setRowCount(0)
        history = get_query_history()
        for row_idx, record in enumerate(history):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(record.get("query_time", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(record.get("card_no", ""))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(record.get("bin_code", ""))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(record.get("bank_name", ""))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(record.get("card_type", ""))))
            self.table.setItem(
                row_idx,
                5,
                QTableWidgetItem(str(record.get("card_length", "") or "")),
            )
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(record.get("source", ""))))

    def refresh_history(self):
        clear_failed_history()
        self.load_history()

    def manual_search(self):
        if not self.signal_sender:
            return

        text = self.search_input.text().strip()
        card_number = "".join(ch for ch in text if ch.isdigit())
        if not card_number:
            return

        self.search_input.setText("查询中...")

        import threading

        def _do_query():
            record = perform_full_query(card_number, self.signal_sender)
            self.signal_sender.show_popup_signal.emit(card_number, record, None)
            QTimer.singleShot(0, lambda: self.search_input.setText(""))

        threading.Thread(target=_do_query, daemon=True).start()

    def clear_history(self):
        answer = QMessageBox.question(
            self,
            "确认清除",
            "确定要清空全部查询历史吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        clear_all_history()
        self.load_history()
        QMessageBox.information(self, "完成", "查询历史已清空")

    def import_bin_db(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的 BIN 码表",
            "",
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        try:
            count = import_excel_to_db(file_path)
            QMessageBox.information(self, "导入完成", f"成功导入 {count} 条 BIN 数据")
        except Exception as exc:
            logger.error("Import BIN table failed: %s", exc)
            QMessageBox.warning(self, "导入失败", str(exc))

    def export_bin_db(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出位置",
            "BIN码表模板.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not save_path:
            return

        try:
            import pandas as pd

            template_headers = ["BIN码", "银行简称", "银行名称", "卡类型", "卡号长度", "来源"]
            df = pd.DataFrame(columns=template_headers)
            df.to_excel(save_path, index=False)
            QMessageBox.information(self, "导出完成", f"已导出空模板（仅标题）:\n{save_path}")
        except Exception as exc:
            logger.error("Export BIN template failed: %s", exc)
            QMessageBox.warning(self, "导出失败", str(exc))
