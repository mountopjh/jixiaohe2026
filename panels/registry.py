from __future__ import annotations

from panels.base import PanelModule
from panels.bin_query_panel import BinQueryPanel


class PanelRegistry:
    def __init__(self, panels: list[PanelModule], primary_id: str) -> None:
        self._panels = {panel.panel_id: panel for panel in panels}
        self._primary_id = primary_id

    def panel_ids(self) -> list[str]:
        return list(self._panels.keys())

    def get_panel(self, panel_id: str) -> PanelModule | None:
        return self._panels.get(panel_id)

    def get_primary_id(self) -> str:
        return self._primary_id

    def get_primary_widget(self):
        panel = self.get_panel(self._primary_id)
        return panel.get_widget() if panel is not None else None

    def refresh_visible_panels(self) -> None:
        for panel in self._panels.values():
            if panel.has_widget() and panel.get_widget().isVisible():
                panel.refresh()


def build_default_registry(signal_sender) -> PanelRegistry:
    primary = BinQueryPanel(signal_sender)
    return PanelRegistry([primary], primary.panel_id)
