# -*- coding: utf-8 -*-
"""
Toggle switch widget builder.
"""

import tkinter as tk
from typing import Callable, Optional, Dict


def build_toggle_switch(parent, theme, label: str, var: tk.BooleanVar,
                       callback: Optional[Callable],
                       switch_drawers: Dict[int, Callable]) -> tk.Frame:
    """
    Build a toggle switch widget.
    
    Args:
        parent: Parent widget
        theme: Theme object with color attributes
        label: Label text
        var: Tkinter BooleanVar bound to switch
        callback: Optional callback when toggled
        switch_drawers: Dictionary to store drawer function by var id
    
    Returns:
        Frame containing the toggle switch
    """
    row = tk.Frame(parent, bg=theme.background)
    row.pack(fill="x", padx=16, pady=4)
    
    tk.Label(row, text=label, font=("Segoe UI", 10),
             bg=theme.background, fg=theme.foreground,
             width=18, anchor="w").pack(side="left")
    
    switch_frame = tk.Frame(row, bg=theme.background)
    switch_frame.pack(side="right")
    
    switch_canvas = tk.Canvas(switch_frame, width=44, height=24,
                             bg=theme.background, highlightthickness=0,
                             cursor="hand2")
    switch_canvas.pack()
    
    def draw_switch():
        """Draw the toggle switch based on current state."""
        switch_canvas.delete("all")
        is_on = var.get()
        
        bg_color = theme.accent if is_on else theme.background_secondary
        knob_color = "white" if is_on else theme.foreground_dim
        knob_x = 28 if is_on else 12
        
        switch_canvas.create_oval(2, 2, 22, 22, fill=bg_color, outline="")
        switch_canvas.create_rectangle(12, 2, 32, 22, fill=bg_color, outline="")
        switch_canvas.create_oval(22, 2, 42, 22, fill=bg_color, outline="")
        
        switch_canvas.create_oval(knob_x - 8, 4, knob_x + 8, 20,
                                 fill=knob_color, outline="")
    
    def toggle():
        """Toggle the switch state."""
        var.set(not var.get())
        draw_switch()
        if callback:
            callback()
    
    switch_canvas.bind("<Button-1>", lambda e: toggle())
    
    switch_drawers[id(var)] = draw_switch
    
    draw_switch()
    
    return row
