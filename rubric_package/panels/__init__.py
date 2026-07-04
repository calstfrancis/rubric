"""Embedded editor panels for Rubric (as opposed to standalone windows or dialogs)."""

from .preamble_panel import PreamblePanel
from .hymn_lookup_panel import HymnLookupPanel
from .order_panel import OrderPanel
from .main_chrome import MainChrome
from .palette_panel import PalettePanel

__all__ = ["PreamblePanel", "HymnLookupPanel", "OrderPanel", "MainChrome", "PalettePanel"]
