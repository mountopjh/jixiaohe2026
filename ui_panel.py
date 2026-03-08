from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QPushButton, QLabel, 
                             QHeaderView, QAbstractItemView, QLineEdit, QMenu, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
import csv
import os
import logging

from query_engine import get_query_history, clear_failed_history
from data_manager import get_db_connection, import_excel_to_db

logger = logging.getLogger(__name__)class MainPanel(QWidget):
    def __init__(self, signal_sender=None, parent=None):
        super().__init__(parent)
        self.signal_sender = signal_sender
        self.setWindowTitle("纪小盒-银行BIN码  登录账户：--")
        self.setMinimumSize(800, 500)
        self.setStyleSheet("""
            QWidget {
                background-color: #F5F6FA;
                color: #1A1A2E;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
            }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE1EC;
                border-radius: 6px;
                gridline-color: #EEF0F8;
                selection-background-color: #D0E8FF;
                selection-color: #1A1A2E;
            }
            QHeaderView::section {
                background-color: #EEF0F8;
                padding: 7px 5px;
                border: none;
                border-right: 1px solid #DDE1EC;
                border-bottom: 1px solid #DDE1EC;
                font-weight: bold;
                color: #333355;
                font-size: 13px;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #C8CBDA;
                border-radius: 6px;
                padding: 6px 14px;
                color: #1A1A2E;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #EEF0F8;
                border-color: #007ACC;
                color: #007ACC;
            }
            QPushButton:pressed {
                background-color: #D0E8FF;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #C8CBDA;
                border-radius: 5px;
                padding: 7px 10px;
                color: #1A1A2E;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #007ACC;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        # No inner title label - it's shown in the window title bar instead
        
        header_layout.addStretch()
        
        # User badge
        from bmob_client import get_current_username
        uname = get_current_username()
        if uname:
            lbl_user = QLabel(f"👤 {uname}")
            lbl_user.setStyleSheet("""
                background-color: #E8F0FE; 
                color: #1A1A2E; 
                padding: 5px 12px; 
                border-radius: 12px; 
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #C8CBDA;
            """)
            header_layout.addWidget(lbl_user)
        
        btn_refresh = QPushButton("刷新记录 ↻")
        btn_refresh.clicked.connect(self.load_history)
        
        btn_clear = QPushButton("清除未查到的记录 🗑")
        btn_clear.clicked.connect(self.clear_history)
        
        btn_import = QPushButton("导入 BIN库 (.xlsx) 📥")
        btn_import.clicked.connect(self.import_bin_db)
        
        btn_export = QPushButton("导出 BIN库 (.xlsx) 📤")
        btn_export.clicked.connect(self.export_bin_db)
        
        header_layout.addSpacing(15)
        header_layout.addWidget(btn_refresh)
        header_layout.addWidget(btn_clear)
        header_layout.addWidget(btn_import)
        header_layout.addWidget(btn_export)
        layout.addLayout(header_layout)
        
        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("手动输入卡号或BIN码查询... (支持直接右键粘贴，无格式限制)")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D30;
                border: 1px solid #007ACC;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #4DB8FF;
            }
        """)
        
        btn_search = QPushButton("手动查询 🔍")
        btn_search.setStyleSheet("padding: 8px 20px; font-size: 14px;")
        btn_search.clicked.connect(self.manual_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "查询时间", "提取到的卡号", "识别到的BIN码", "归属银行", "卡类型", "数据来源"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.table)
        
        # Load initial data
        self.load_history()
        
    def load_history(self):
        self.table.setRowCount(0)
        history = get_query_history()
        for row_idx, record in enumerate(history):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(record.get('query_time', ''))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(record.get('card_no', '')))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(record.get('bin_code', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(record.get('bank_name', '')))
            self.table.setItem(row_idx, 4, QTableWidgetItem(record.get('card_type', '')))
            self.table.setItem(row_idx, 5, QTableWidgetItem(record.get('source', '')))
            
    def manual_search(self):
        text = self.search_input.text().strip()
        if text and self.signal_sender:
            card_number = "".join([c for c in text if c.isdigit()])
            if card_number:
                # Dispatch the search process to the global background task logic if possible,
                # or here we do it synchronously since it's user triggered manual
                from query_engine import perform_full_query
                self.search_input.setText("查询中...")
                # Avoid freezing UI too long, ideally this should be a QThread, 
                # but for simplicity we do it inline or allow short UI block.
                # Actually, to be safe, emit the signal and handle it in main if we set that up,
                # or just run it inline. Let's run it inline for now.
                import threading
                def _do_query():
                    record = perform_full_query(card_number)
                    self.signal_sender.show_popup_signal.emit(card_number, record)
                    # Use QTimer to reset text on main thread
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.search_input.setText(""))
                
                threading.Thread(target=_do_query, daemon=True).start()
            
    def clear_history(self):
        clear_failed_history()
        self.load_history()
        QMessageBox.information(self, "清理成功", "已成功清除未查到结果的历史记录！")
            
    def import_bin_db(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择要导入的 XLSX 文件", "", "Excel Files (*.xlsx)")
        if file_path:
            try:
                count = import_excel_to_db(file_path)
                QMessageBox.information(self, "导入成功", f"成功导入 {count} 条新的 BIN 码记录到本地库！")
            except Exception as e:
                logger.error(f"Import Error: {e}")
                QMessageBox.warning(self, "导入失败", f"导入文件时发生错误：\n{str(e)}")

    def export_bin_db(self):
        try:
            import pandas as pd
            conn = get_db_connection()
            # Rename columns to match Chinese directly in SQL
            query = '''
            SELECT 
                bin_code as 'BIN码', 
                bank_abbr as '银行缩写', 
                bank_name as '银行名称', 
                card_type as '卡类型', 
                card_length as '卡号长度', 
                source as '数据来源'
            FROM bin_data
            '''
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Add sequence column at the front
            df.insert(0, '序号', range(1, len(df) + 1))
            
            export_path = os.path.join(os.getcwd(), 'exported_bin_db.xlsx')
            df.to_excel(export_path, index=False)
            
            QMessageBox.information(self, "导出成功", f"数据库已成功导出至：\n{export_path}")
            
        except Exception as e:
            logger.error(f"Export Error: {e}")
            QMessageBox.warning(self, "导出失败", f"导出数据库时发生错误：\n{str(e)}")
