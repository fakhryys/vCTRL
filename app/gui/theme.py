# -*- coding: utf-8 -*-
"""
Theme definitions and management.
"""

from dataclasses import dataclass
import ctypes
import logging

from ..constants import DWMWA_USE_IMMERSIVE_DARK_MODE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Theme:
    """Color scheme definition."""
    
    accent: str
    background: str
    background_secondary: str
    foreground: str
    foreground_dim: str
    success: str
    error: str
    warning: str


DARK_THEME = Theme(
    accent="#5865F2",
    background="#1e1f2e",
    background_secondary="#2a2b3d",
    foreground="#e0e0f0",
    foreground_dim="#8888aa",
    success="#43b581",
    error="#ed4245",
    warning="#faa61a",
)

LIGHT_THEME = Theme(
    accent="#5865F2",
    background="#ffffff",
    background_secondary="#f0f0f0",
    foreground="#2e2e2e",
    foreground_dim="#666666",
    success="#2d8659",
    error="#d32f2f",
    warning="#f57c00",
)


def get_theme(name: str) -> Theme:
    """Get theme by name."""
    if name.lower() == "dark":
        return DARK_THEME
    else:
        return LIGHT_THEME


def set_window_title_bar_theme(window_id: int, is_dark: bool):
    """
    Set Windows title bar to dark or light mode.
    
    Args:
        window_id: Window handle (from winfo_id())
        is_dark: True for dark mode, False for light mode
    """
    try:
        hwnd = ctypes.windll.user32.GetParent(window_id)
        value = ctypes.c_int(1 if is_dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
    except Exception as e:
        logger.warning(f"Failed to set title bar theme: {e}")
