# -*- coding: utf-8 -*-
"""
Slider widget builder.
"""

import tkinter as tk
from typing import Callable


def build_slider(parent, theme, label: str, var: tk.DoubleVar,
                from_: float, to: float, resolution: float,
                format_func: Callable[[float], str],
                callback: Callable[[float], None]) -> tuple:
    """
    Build a labeled slider widget.
    
    Args:
        parent: Parent widget
        theme: Theme object with color attributes
        label: Label text
        var: Tkinter variable bound to slider
        from_: Minimum value
        to: Maximum value
        resolution: Step size
        format_func: Function to format value for display
        callback: Callback when value changes
    
    Returns:
        Tuple of (frame, update_label_func) where update_label_func refreshes the value label
    """
    row = tk.Frame(parent, bg=theme.background)
    row.pack(fill="x", padx=16, pady=4)
    
    tk.Label(row, text=label, font=("Segoe UI", 10),
             bg=theme.background, fg=theme.foreground,
             width=14, anchor="w").pack(side="left")
    
    value_label = tk.Label(row, text=format_func(var.get()),
                          font=("Consolas", 10),
                          bg=theme.background, fg=theme.accent,
                          width=6, anchor="e")
    value_label.pack(side="right")
    
    def on_change(val):
        value_label.config(text=format_func(float(val)))
        callback(float(val))
    
    def update_label():
        """Update the value label to reflect current variable value."""
        value_label.config(text=format_func(var.get()))
    
    scale = tk.Scale(
        row, variable=var, from_=from_, to=to,
        resolution=resolution, orient="horizontal",
        showvalue=False, command=on_change,
        bg=theme.background, fg=theme.foreground,
        troughcolor=theme.background_secondary,
        activebackground=theme.accent, highlightthickness=0,
        sliderlength=16
    )
    scale.pack(side="left", fill="x", expand=True, padx=(4, 8))
    
    return row, update_label
