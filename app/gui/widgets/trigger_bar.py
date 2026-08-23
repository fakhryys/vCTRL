# -*- coding: utf-8 -*-
"""
Trigger progress bar widget builder.
"""

import tkinter as tk
from tkinter import ttk


def build_trigger_bar(parent, theme, label: str, var: tk.IntVar) -> tuple:
    """
    Build a trigger progress bar with label and percentage.
    
    Args:
        parent: Parent widget
        theme: Theme object with color attributes
        label: Label text (e.g., "LT" or "RT")
        var: IntVar for progress (0-100)
    
    Returns:
        Tuple of (progressbar, percentage_label)
    """
    row = tk.Frame(parent, bg=theme.background)
    row.pack(fill="x", padx=16, pady=3)
    
    tk.Label(row, text=label, font=("Segoe UI", 10),
             bg=theme.background, fg=theme.foreground,
             width=14, anchor="w").pack(side="left")
    
    pct_lbl = tk.Label(row, text="  0%", font=("Consolas", 10),
                      bg=theme.background, fg=theme.accent,
                      width=6, anchor="e")
    pct_lbl.pack(side="right")
    
    style_name = f"{label}.Horizontal.TProgressbar"
    style = ttk.Style()
    style.theme_use("default")
    style.configure(style_name,
                   troughcolor=theme.background_secondary,
                   background=theme.accent,
                   thickness=14)
    
    bar = ttk.Progressbar(row, style=style_name,
                         variable=var, maximum=100,
                         orient="horizontal")
    bar.pack(side="left", fill="x", expand=True, padx=(4, 8))
    
    return bar, pct_lbl
