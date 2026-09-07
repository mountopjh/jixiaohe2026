# Panels Module Guide

This project now supports pluggable panels via `panels/registry.py`.

## Current Structure

- `panels/base.py`
  - Defines `PanelModule` contract.
- `panels/bin_query_panel.py`
  - Wraps existing BIN query panel (`ui_panel.MainPanel`).
- `panels/registry.py`
  - Registers and manages all panels.
- `main.py`
  - Uses registry to open/refresh panels without hard-coding one panel.

## Add Panel 2/3/4

1. Create a new module in `panels/`, e.g. `panels/panel2.py`.
2. Implement a class extending `PanelModule`.
3. Implement:
   - `create_widget(self) -> QWidget`
   - `refresh(self)` (optional but recommended)
4. Register it in `build_default_registry(...)` in `panels/registry.py`.

Example:

```python
from .base import PanelModule

class Panel2(PanelModule):
    panel_id = "panel2"
    panel_name = "Panel 2"

    def __init__(self, signal_sender):
        super().__init__()
        self._signal_sender = signal_sender

    def create_widget(self):
        from PyQt6.QtWidgets import QWidget
        return QWidget()
```

Then in `build_default_registry(...)`:

```python
registry.register(Panel2(signal_sender))
```

## Behavior

- Tray menu now includes a `Panels` submenu.
- `show_main_panel()` opens the primary panel from registry.
- Query completion refreshes **all visible panels** via registry.
