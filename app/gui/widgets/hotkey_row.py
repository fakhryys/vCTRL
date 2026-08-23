# -*- coding: utf-8 -*-
"""
Hotkey row widget builder.
"""

import tkinter as tk
from typing import Callable, List


def build_hotkey_row(parent, theme, label: str, var: tk.StringVar,
                    hk_name: str, on_listen: Callable, on_clear: Callable,
                    entry_widgets: List[tk.Label],
                    readonly: bool = False) -> tk.Label:
    """
    Build a hotkey configuration row.
    
    Args:
        parent: Parent widget
        theme: Theme object with color attributes
        label: Label text
        var: StringVar containing hotkey combo
        hk_name: Internal name for this hotkey
        on_listen: Callback to start listening for hotkey
        on_clear: Callback to clear hotkey
        entry_widgets: List to track entry widgets for color updates
        readonly: If True, make non-editable
    
    Returns:
        The entry label widget
    """
    row = tk.Frame(parent, bg=theme.background)
    row.pack(fill="x", padx=16, pady=3)
    
    tk.Label(row, text=label, font=("Segoe UI", 10),
             bg=theme.background, fg=theme.foreground,
             width=14, anchor="w").pack(side="left")
    
    if not readonly:
        clear_btn = tk.Button(
            row, text="\u2715", font=("Segoe UI", 9),
            bg=theme.background_secondary, fg=theme.error,
            activebackground=theme.background_secondary,
            activeforeground=theme.error,
            relief="flat", width=6, pady=2, cursor="hand2",
            command=lambda: on_clear(hk_name, var)
        )
        clear_btn.pack(side="right")
    
    entry_frame = tk.Frame(row, bg=theme.background_secondary,
                          relief="flat", bd=1, highlightthickness=1,
                          highlightbackground=theme.background_secondary)
    entry_frame.pack(side="left", fill="x", expand=True, padx=(4, 8))
    
    entry_label = tk.Label(
        entry_frame, textvariable=var,
        font=("Consolas", 10),
        bg=theme.background_secondary, fg=theme.foreground,
        anchor="w", padx=4, pady=4,
        cursor="hand2" if not readonly else "arrow"
    )
    entry_label.pack(fill="x")
    
    if not readonly:
        entry_label.bind("<Button-1>",
                        lambda e: on_listen(hk_name, entry_label, var))
    
    entry_widgets.append(entry_label)
    
    return entry_label
