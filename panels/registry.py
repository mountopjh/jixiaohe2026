from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Optional

from PyQt6.QtWidgets import QWidget

from .base import PanelModule
from .bin_query_panel import BinQueryPanel


class PanelRegistry:
    """Central registry for all independent feature panels."""

    def __init__(self) -> None:
        self._panels: "OrderedDict[str, PanelModule]" = OrderedDict()
        self._primary_id: Optional[str] = None

    def register(self, panel: PanelModule, primary: bool = False) -> None:
        self._panels[panel.panel_id] = panel
        if primary or self._primary_id is None:
            self._primary_id = panel.panel_id

    def panel_ids(self) -> Iterable[str]:
        return self._panels.keys()

    def get_panel(self, panel_id: str) -> Optional[PanelModule]:
        return self._panels.get(panel_id)

    def get_widget(self, panel_id: str) -> Optional[QWidget]:
        panel = self.get_panel(panel_id)
        if panel is None:
            return None
        return panel.get_widget()

    def get_primary_id(self) -> Optional[str]:
        return self._primary_id

    def get_primary_widget(self) -> Optional[QWidget]:
        if self._primary_id is None:
            return None
        return self.get_widget(self._primary_id)

    def refresh_visible_panels(self) -> None:
        for panel in self._panels.values():
            if not panel.has_widget():
                continue
            widget = panel.get_widget()
            if widget.isVisible():
                panel.refresh()


def build_default_registry(signal_sender) -> PanelRegistry:
    """Register existing panels. Add Panel2/3/4 here later."""
    registry = PanelRegistry()
    registry.register(BinQueryPanel(signal_sender), primary=True)
    return registry
