# -*- coding: utf-8 -*-
"""
Data models for input configuration.
"""

from dataclasses import dataclass


@dataclass
class HotkeyConfig:
    """Configuration for all application hotkeys."""
    
    toggle: str = "capslock"
    center: str = "`"
    trigger_up: str = "w"
    trigger_down: str = "s"
    lt_up: str = "q"
    lt_down: str = "a"
    rt_up: str = "e"
    rt_down: str = "d"
    switch_stick: str = "alt+x"
    reset_triggers: str = "alt+t"
    crosshair: str = "n"
    trigger_overlay: str = "m"
    
    separate_triggers: bool = False
    reset_opposite_trigger: bool = False
    trigger_intensity: float = 0.1
