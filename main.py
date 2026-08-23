# -*- coding: utf-8 -*-
"""
vCTRL - Mouse to Virtual Joystick
Entry point for the application.
"""

import ctypes
import sys
import logging

from app.gui.app import App
from app.controller import MouseJoystickMapper
from app.input import KeyboardHook
from app.config import ConfigManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def set_dpi_awareness():
    """Enable DPI awareness for crisp rendering on high-DPI displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    set_dpi_awareness()
    
    config_manager = ConfigManager()
    config = config_manager.load()
    
    mapper = MouseJoystickMapper()
    keyboard_hook = KeyboardHook(mapper)
    
    app = App(mapper, keyboard_hook, config_manager, config)
    app.mainloop()


if __name__ == "__main__":
    main()
