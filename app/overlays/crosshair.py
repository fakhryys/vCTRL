# -*- coding: utf-8 -*-
"""
Crosshair overlay window.
"""

import tkinter as tk
import ctypes
import logging

from ..constants import GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT

logger = logging.getLogger(__name__)


class CrosshairOverlay:
    """Transparent overlay window displaying a crosshair at screen center."""
    
    def __init__(self):
        self._window = None
        self._visible = False
    
    def show(self):
        """Show the crosshair overlay."""
        if self._window:
            return
        
        self._visible = True
        self._window = tk.Toplevel()
        self._window.title("Crosshair overlay")
        self._window.attributes("-topmost", True)
        self._window.attributes("-transparentcolor", "black")
        self._window.overrideredirect(True)
        
        screen_width = self._window.winfo_screenwidth()
        screen_height = self._window.winfo_screenheight()
        
        size = 10
        x = (screen_width - size) // 2
        y = (screen_height - size) // 2
        self._window.geometry(f"{size}x{size}+{x}+{y}")
        
        canvas = tk.Canvas(self._window, width=size, height=size,
                          bg="black", highlightthickness=0)
        canvas.pack()
        
        canvas.create_oval(2, 2, size - 2, size - 2, fill="white", outline="")
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            styles = styles | WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles)
        except Exception as e:
            logger.error(f"Failed to make crosshair click-through: {e}")
    
    def hide(self):
        """Hide the crosshair overlay."""
        if self._window:
            self._window.destroy()
            self._window = None
        self._visible = False
    
    def is_visible(self) -> bool:
        """Check if crosshair is currently visible."""
        return self._visible
