from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from PyQt6.QtWidgets import QWidget


class PanelModule(ABC):
    """Base contract for all pluggable panels."""

    panel_id: str
    panel_name: str

    def __init__(self) -> None:
        self._widget: Optional[QWidget] = None

    @abstractmethod
    def create_widget(self) -> QWidget:
        """Create and return the concrete widget for this panel."""

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self.create_widget()
        return self._widget

    def has_widget(self) -> bool:
        return self._widget is not None

    def refresh(self) -> None:
        """Refresh panel data if needed. Optional for each panel."""
        return
