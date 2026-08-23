# -*- coding: utf-8 -*-
"""
Windows constants and application configuration values.
"""

# Win32 modifier flags
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Win32 virtual key codes
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B

# Win32 hook constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

# Win32 window style flags
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20

# DWM constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

# Application constants
POLL_HZ = 120
CONFIG_FILENAME = "config.json"
PROFILES_DIRNAME = "profiles"

# Modifier name to flag mapping
MODIFIER_MAP = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

# Virtual key name to VK code mapping
VK_CODE_MAP = {
    # Letters
    **{chr(c): ord(chr(c).upper()) for c in range(ord('a'), ord('z') + 1)},
    # Numbers
    **{str(d): ord(str(d)) for d in range(10)},
    # Function keys
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    # Special keys
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "backspace": 0x08, "escape": 0x1B,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    # Arrow keys
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    # Numpad
    "numpad0": 0x60, "numpad1": 0x61, "numpad2": 0x62, "numpad3": 0x63,
    "numpad4": 0x64, "numpad5": 0x65, "numpad6": 0x66, "numpad7": 0x67,
    "numpad8": 0x68, "numpad9": 0x69,
    # Symbols
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
    # Lock keys
    "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
}
