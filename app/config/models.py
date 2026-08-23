# -*- coding: utf-8 -*-
"""
Configuration data models.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class AppConfig:
    """Application configuration settings."""
    
    sensitivity: float = 1.0
    deadzone: float = 0.05
    stick: str = "Left"
    hotkey_toggle: str = "capslock"
    hotkey_center: str = "`"
    hotkey_trigger_up: str = "w"
    hotkey_trigger_down: str = "s"
    hotkey_lt_up: str = "s"
    hotkey_lt_down: str = "a"
    hotkey_rt_up: str = "w"
    hotkey_rt_down: str = "d"
    hotkey_switch_stick: str = "alt+x"
    hotkey_reset_triggers: str = "alt+t"
    hotkey_crosshair: str = "alt+n"
    hotkey_trigger_overlay: str = "alt+m"
    theme: str = "light"
    crosshair: bool = False
    trigger_overlay: bool = False
    separate_triggers: bool = False
    reset_opposite_trigger: bool = False
    run_minimized: bool = False
    trigger_intensity: float = 0.1
    show_status: bool = True
    last_profile: str = "Default"
    invert_y: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary, using defaults for missing keys."""
        defaults = cls()
        filtered = {k: v for k, v in data.items() if hasattr(defaults, k)}
        return cls(**filtered)
    
    def validate(self):
        """Validate configuration values and clamp to acceptable ranges."""
        self.sensitivity = max(0.1, min(3.0, self.sensitivity))
        self.deadzone = max(0.0, min(0.5, self.deadzone))
        self.trigger_intensity = max(0.01, min(0.5, self.trigger_intensity))
        
        if self.stick not in ("Left", "Right"):
            self.stick = "Left"
        
        if self.theme not in ("dark", "light"):
            self.theme = "light"
