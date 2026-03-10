from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QWidget

from ui_panel import MainPanel
from .base import PanelModule


class BinQueryPanel(PanelModule):
    panel_id = "bin_query"
    panel_name = "BIN 查询面板"

    def __init__(self, signal_sender) -> None:
        super().__init__()
        self._signal_sender = signal_sender
        self._panel: Optional[MainPanel] = None

    def create_widget(self) -> QWidget:
        self._panel = MainPanel(self._signal_sender)
        return self._panel

    def refresh(self) -> None:
        if self._panel is not None:
            self._panel.load_history()
