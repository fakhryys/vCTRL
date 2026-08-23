# -*- coding: utf-8 -*-
"""
Profile message overlay window.
"""

import tkinter as tk
import logging

logger = logging.getLogger(__name__)


class ProfileMessageOverlay:
    """Transparent overlay window displaying profile name temporarily."""
    
    def __init__(self):
        self._window = None
        self._hide_timer = None
    
    def show(self, profile_name: str, duration_ms: int = 5000):
        """
        Show the profile message overlay.
        
        Args:
            profile_name: Name of the profile to display
            duration_ms: Duration in milliseconds to show the overlay (default: 5000)
        """
        # Hide any existing overlay first
        self.hide()
        
        self._window = tk.Toplevel()
        self._window.title("Profile Message")
        self._window.attributes("-topmost", True)
        self._window.attributes("-transparentcolor", "black")
        self._window.overrideredirect(True)
        
        screen_width = self._window.winfo_screenwidth()
        screen_height = self._window.winfo_screenheight()
        
        # Create frame with padding
        frame = tk.Frame(self._window, bg="#2C2C2C", relief="flat", bd=0)
        frame.pack(padx=2, pady=2)
        
        # Inner frame for content
        inner_frame = tk.Frame(frame, bg="#2C2C2C")
        inner_frame.pack(padx=12, pady=8)
        
        # Profile label
        label = tk.Label(
            inner_frame,
            text=f"Current Profile: {profile_name}",
            font=("Segoe UI", 11),
            bg="#2C2C2C",
            fg="white",
            padx=8,
            pady=4
        )
        label.pack()
        
        # Update to get actual size
        self._window.update_idletasks()
        width = self._window.winfo_reqwidth()
        height = self._window.winfo_reqheight()
        
        # Position at top right corner with margin
        margin = 20
        x = screen_width - width - margin
        y = margin
        
        self._window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Schedule auto-hide
        self._hide_timer = self._window.after(duration_ms, self.hide)
    
    def hide(self):
        """Hide the profile message overlay."""
        if self._hide_timer:
            try:
                self._window.after_cancel(self._hide_timer)
            except:
                pass
            self._hide_timer = None
        
        if self._window:
            try:
                self._window.destroy()
            except:
                pass
            self._window = None
