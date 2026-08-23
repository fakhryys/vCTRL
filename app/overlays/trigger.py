# -*- coding: utf-8 -*-
"""
Trigger overlay window showing LT/RT values.
"""

import tkinter as tk
import ctypes
import logging

from ..constants import GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT

logger = logging.getLogger(__name__)


class TriggerOverlay:
    """Transparent overlay window displaying LT/RT trigger bars at top left."""
    
    def __init__(self):
        self._window = None
        self._visible = False
        self._lt_canvas = None
        self._rt_canvas = None
        self._lt_bar = None
        self._rt_bar = None
        self._lt_text = None
        self._rt_text = None
        self._lt_value_canvas = None
        self._rt_value_canvas = None
        self._lt_value = 0.0
        self._rt_value = 0.0
    
    def show(self):
        """Show the trigger overlay."""
        if self._window:
            return
        
        self._visible = True
        self._window = tk.Toplevel()
        self._window.title("Triggers")
        self._window.attributes("-topmost", True)
        self._window.attributes("-transparentcolor", "black")
        self._window.overrideredirect(True)
        
        label_width = 30
        bar_width = 260
        value_width = 40
        bar_height = 16
        spacing = 8
        margin = 20
        total_width = label_width + bar_width + value_width
        total_height = (bar_height * 2) + spacing
        
        x = margin
        y = margin
        self._window.geometry(f"{total_width}x{total_height}+{x}+{y}")
        self._window.config(bg="black")
        
        lt_frame = tk.Frame(self._window, bg="black")
        lt_frame.pack(pady=(0, spacing))
        
        lt_label_canvas = tk.Canvas(lt_frame, width=label_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        lt_label_canvas.pack(side="left")
        lt_label_canvas.create_text(
            5, bar_height // 2, text="LT",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        self._lt_canvas = tk.Canvas(lt_frame, width=bar_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        self._lt_canvas.pack(side="left")
        
        self._lt_canvas.create_rectangle(
            0, 0, bar_width, bar_height, fill="", outline="white", width=2
        )
        self._lt_bar = self._lt_canvas.create_rectangle(
            2, 2, 2, bar_height - 2, fill="white", outline=""
        )
        
        self._lt_value_canvas = tk.Canvas(lt_frame, width=value_width, height=bar_height,
                                         bg="black", highlightthickness=0)
        self._lt_value_canvas.pack(side="left")
        self._lt_text = self._lt_value_canvas.create_text(
            5, bar_height // 2, text="0",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        rt_frame = tk.Frame(self._window, bg="black")
        rt_frame.pack()
        
        rt_label_canvas = tk.Canvas(rt_frame, width=label_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        rt_label_canvas.pack(side="left")
        rt_label_canvas.create_text(
            5, bar_height // 2, text="RT",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        self._rt_canvas = tk.Canvas(rt_frame, width=bar_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        self._rt_canvas.pack(side="left")
        
        self._rt_canvas.create_rectangle(
            0, 0, bar_width, bar_height, fill="", outline="white", width=2
        )
        self._rt_bar = self._rt_canvas.create_rectangle(
            2, 2, 2, bar_height - 2, fill="white", outline=""
        )
        
        self._rt_value_canvas = tk.Canvas(rt_frame, width=value_width, height=bar_height,
                                         bg="black", highlightthickness=0)
        self._rt_value_canvas.pack(side="left")
        self._rt_text = self._rt_value_canvas.create_text(
            5, bar_height // 2, text="0",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        self.update_values(self._lt_value, self._rt_value)
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            styles = styles | WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles)
        except Exception as e:
            logger.error(f"Failed to make trigger overlay click-through: {e}")
    
    def hide(self):
        """Hide the trigger overlay."""
        if self._window:
            self._window.destroy()
            self._window = None
            self._lt_canvas = None
            self._rt_canvas = None
        self._visible = False
    
    def update_values(self, lt: float, rt: float):
        """Update trigger bar values (0.0 to 1.0)."""
        self._lt_value = lt
        self._rt_value = rt
        
        if not self._visible or not self._lt_canvas:
            return
        
        bar_width = 260
        bar_height = 16
        border = 2
        
        lt_width = int((bar_width - border * 2) * lt) + border
        self._lt_canvas.coords(self._lt_bar, border, border, lt_width, bar_height - border)
        self._lt_value_canvas.itemconfig(self._lt_text, text=str(int(lt * 100)))
        
        rt_width = int((bar_width - border * 2) * rt) + border
        self._rt_canvas.coords(self._rt_bar, border, border, rt_width, bar_height - border)
        self._rt_value_canvas.itemconfig(self._rt_text, text=str(int(rt * 100)))
    
    def is_visible(self) -> bool:
        """Check if trigger overlay is currently visible."""
        return self._visible
