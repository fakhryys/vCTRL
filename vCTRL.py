# -*- coding: utf-8 -*-
"""
vCTRL - Mouse to Virtual Joystick
Maps mouse screen position to well-known USB game controller left and right stick axes via ViGEmBus.

Requirements:
    pip install vgamepad pystray Pillow

ViGEmBus driver is installed automatically by vgamepad on first run.
"""

import threading
import time
import math
import json
import os
import tkinter as tk
from tkinter import ttk
import ctypes
import sys

# ── optional tray support ─────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# ── vgamepad ──────────────────────────────────────────────────────────────────
try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    VGAMEPAD_AVAILABLE = False

# ── Win32 constants ───────────────────────────────────────────────────────────
# Pure ctypes - no pywin32 needed
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_CONTROL = 0x11

# ─────────────────────────────────────────────────────────────────────────────
# Config persistence
# ─────────────────────────────────────────────────────────────────────────────

# For PyInstaller: use the directory where the .exe is located (not temp dir)
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APP_DIR = os.path.dirname(sys.executable)
    # PyInstaller extracts bundled files to sys._MEIPASS
    RESOURCE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    # Running as script
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR

CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "sensitivity": 1.0,
    "deadzone": 0.05,
    "stick": "Left",
    "hotkey_toggle": "capslock",
    "hotkey_center": "`",
    "hotkey_trigger_up": "w",
    "hotkey_trigger_down": "s",
    "hotkey_lt_up": "q",
    "hotkey_lt_down": "a",
    "hotkey_rt_up": "e",
    "hotkey_rt_down": "d",
    "hotkey_switch_stick": "alt+x",
    "hotkey_reset_triggers": "alt+t",
    "hotkey_crosshair": "n",
    "hotkey_trigger_overlay": "m",
    "theme": "light",  # "dark" or "light"
    "crosshair": False,  # Show crosshair overlay
    "trigger_overlay": False,  # Show trigger overlay
    "separate_triggers": False,  # Separate LT/RT trigger controls
    "reset_opposite_trigger": False,  # Reset opposite trigger when one is pressed
}

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = dict(DEFAULT_CONFIG)
        cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Hotkey manager  (Win32 RegisterHotKey)
# ─────────────────────────────────────────────────────────────────────────────

# Map modifier names → win32 MOD_* flags (use literals; constants match win32con values)
_MOD_MAP = {
    "ctrl":    0x0002,  # MOD_CONTROL
    "control": 0x0002,
    "alt":     0x0001,  # MOD_ALT
    "shift":   0x0004,  # MOD_SHIFT
    "win":     0x0008,  # MOD_WIN
}

# Virtual-key names → VK codes  (common keys; full VK table not needed)
_VK_MAP = {
    **{chr(c): ord(chr(c).upper()) for c in range(ord('a'), ord('z')+1)},
    **{str(d): ord(str(d))         for d in range(10)},
    "f1":0x70,"f2":0x71,"f3":0x72,"f4":0x73,"f5":0x74,"f6":0x75,
    "f7":0x76,"f8":0x77,"f9":0x78,"f10":0x79,"f11":0x7A,"f12":0x7B,
    "space":0x20,"enter":0x0D,"tab":0x09,"backspace":0x08,"escape":0x1B,
    "insert":0x2D,"delete":0x2E,"home":0x24,"end":0x23,
    "pageup":0x21,"pagedown":0x22,
    "up":0x26,"down":0x28,"left":0x25,"right":0x27,
    "numpad0":0x60,"numpad1":0x61,"numpad2":0x62,"numpad3":0x63,
    "numpad4":0x64,"numpad5":0x65,"numpad6":0x66,"numpad7":0x67,
    "numpad8":0x68,"numpad9":0x69,
    "`":0xC0,"-":0xBD,"=":0xBB,"[":0xDB,"]":0xDD,
    "\\":0xDC,";":0xBA,"'":0xDE,",":0xBC,".":0xBE,"/":0xBF,
    "capslock":0x14,"numlock":0x90,"scrolllock":0x91,
}

def parse_hotkey(combo: str):
    """
    Parse a combo string like 'ctrl+shift+t' into (mod_flags, vk_code).
    Returns (None, None) on failure.
    """
    if not combo:
        return None, None
    parts = [p.strip().lower() for p in combo.split("+")]
    mods = 0
    vk   = None
    for part in parts:
        if part in _MOD_MAP:
            mods |= _MOD_MAP[part]
        elif part in _VK_MAP:
            vk = _VK_MAP[part]
        else:
            # Try treating it as a raw int (vk code passed as string)
            try:
                vk = int(part)
            except ValueError:
                return None, None
    if vk is None:
        return None, None
    return mods, vk


# ─────────────────────────────────────────────────────────────────────────────
# Trigger hook  (keyboard hook for all hotkeys)
# ─────────────────────────────────────────────────────────────────────────────

_TRIGGER_STEP = 0.1        # trigger delta per key press
_WH_KEYBOARD_LL = 13
_WM_KEYDOWN = 0x0100
_WM_SYSKEYDOWN = 0x0104    # Alt combinations fire SYSKEYDOWN
_VK_MENU = 0x12            # Alt key

# Define KBDLLHOOKSTRUCT for proper memory layout
class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

# We must keep a reference to the ctypes callback to prevent GC
_hook_cb_ref = None

class TriggerHook:
    """
    Single keyboard hook that handles:
    - Configurable trigger up/down hotkeys
    - Configurable toggle hotkey
    - Configurable center hotkey
    - Configurable switch stick hotkey
    - Configurable reset triggers hotkey
    """

    def __init__(self, mapper):
        self._mapper = mapper
        self._hook   = None
        self._thread = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._on_change = None  # callable(lt, rt) or None
        self._on_toggle = None  # callable() or None
        self._on_center = None  # callable() or None
        self._on_switch_stick = None  # callable() or None
        self._on_reset_triggers = None  # callable() or None
        self._on_toggle_crosshair = None  # callable() or None
        self._on_toggle_trigger_overlay = None  # callable() or None

        # Separate triggers mode flag
        self._separate_triggers = False
        self._reset_opposite_trigger = False

        # Hotkey configurations (mod_flags, vk_code)
        self._hk_toggle = (0, 0x14)       # CapsLock
        self._hk_center = (0, 0xC0)       # Backtick
        self._hk_trigger_up   = (0, 0x57) # W  – combined both
        self._hk_trigger_down = (0, 0x53) # S  – combined both
        self._hk_lt_up   = (0, 0x51)      # Q  – LT only
        self._hk_lt_down = (0, 0x41)      # A  – LT only
        self._hk_rt_up   = (0, 0x45)      # E  – RT only
        self._hk_rt_down = (0, 0x44)      # D  – RT only
        self._hk_switch_stick    = (0, 0x09)        # Tab
        self._hk_reset_triggers  = (MOD_ALT, 0x52)  # Alt+R
        self._hk_crosshair       = (0, 0x70)        # F1
        self._hk_trigger_overlay = (0, 0x71)        # F2

    def set_hotkeys(self, toggle_combo: str, center_combo: str,
                    trigger_up_combo: str, trigger_down_combo: str,
                    lt_up_combo: str, lt_down_combo: str,
                    rt_up_combo: str, rt_down_combo: str,
                    switch_stick_combo: str, reset_triggers_combo: str,
                    crosshair_combo: str, trigger_overlay_combo: str,
                    separate_triggers: bool = False,
                    reset_opposite_trigger: bool = False):
        """Update all hotkey configurations from combo strings."""
        self._separate_triggers = separate_triggers
        self._reset_opposite_trigger = reset_opposite_trigger

        def _set(attr, combo):
            if combo:
                mods, vk = parse_hotkey(combo)
                if vk is not None:
                    setattr(self, attr, (mods, vk))

        _set('_hk_toggle',          toggle_combo)
        _set('_hk_center',          center_combo)
        _set('_hk_trigger_up',      trigger_up_combo)
        _set('_hk_trigger_down',    trigger_down_combo)
        _set('_hk_lt_up',           lt_up_combo)
        _set('_hk_lt_down',         lt_down_combo)
        _set('_hk_rt_up',           rt_up_combo)
        _set('_hk_rt_down',         rt_down_combo)
        _set('_hk_switch_stick',    switch_stick_combo)
        _set('_hk_reset_triggers',  reset_triggers_combo)
        _set('_hk_crosshair',       crosshair_combo)
        _set('_hk_trigger_overlay', trigger_overlay_combo)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="TriggerHook")
        self._thread.start()
        self._ready_event.wait(timeout=2.0)

    def stop(self):
        self._stop_event.set()
        try:
            ctypes.windll.user32.PostThreadMessageW(
                self._thread.ident if self._thread else 0,
                0x0012,  # WM_QUIT
                0, 0)
        except Exception:
            pass

    def _check_modifiers(self, required_mods: int) -> bool:
        """Check if the required modifier keys are currently held."""
        if required_mods == 0:
            return True
        
        result = True
        if required_mods & MOD_ALT:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(_VK_MENU) & 0x8000 != 0)
        if required_mods & MOD_CONTROL:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000 != 0)
        if required_mods & MOD_SHIFT:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000 != 0)  # VK_SHIFT
        if required_mods & MOD_WIN:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(0x5B) & 0x8000 != 0)  # VK_LWIN
        
        return result

    def _run(self):
        global _hook_cb_ref
        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(_KBDLLHOOKSTRUCT)
        )

        def low_level_keyboard_proc(nCode, wParam, lParam):
            if nCode >= 0 and (wParam == _WM_KEYDOWN or wParam == _WM_SYSKEYDOWN):
                event = lParam.contents
                vk = event.vkCode

                if self._separate_triggers:
                    # ── Separate LT / RT mode ─────────────────────────────────
                    if vk == self._hk_lt_up[1] and self._check_modifiers(self._hk_lt_up[0]):
                        self._adjust_lt(+_TRIGGER_STEP)
                    elif vk == self._hk_lt_down[1] and self._check_modifiers(self._hk_lt_down[0]):
                        self._adjust_lt(-_TRIGGER_STEP)
                    elif vk == self._hk_rt_up[1] and self._check_modifiers(self._hk_rt_up[0]):
                        self._adjust_rt(+_TRIGGER_STEP)
                    elif vk == self._hk_rt_down[1] and self._check_modifiers(self._hk_rt_down[0]):
                        self._adjust_rt(-_TRIGGER_STEP)
                    elif vk == self._hk_reset_triggers[1] and self._check_modifiers(self._hk_reset_triggers[0]):
                        if self._on_reset_triggers:
                            try: self._on_reset_triggers()
                            except Exception: pass
                    elif vk == self._hk_toggle[1] and self._check_modifiers(self._hk_toggle[0]):
                        if self._on_toggle:
                            try: self._on_toggle()
                            except Exception: pass
                    elif vk == self._hk_center[1] and self._check_modifiers(self._hk_center[0]):
                        if self._on_center:
                            try: self._on_center()
                            except Exception: pass
                    elif vk == self._hk_switch_stick[1] and self._check_modifiers(self._hk_switch_stick[0]):
                        if self._on_switch_stick:
                            try: self._on_switch_stick()
                            except Exception: pass
                    elif vk == self._hk_crosshair[1] and self._check_modifiers(self._hk_crosshair[0]):
                        if self._on_toggle_crosshair:
                            try: self._on_toggle_crosshair()
                            except Exception: pass
                    elif vk == self._hk_trigger_overlay[1] and self._check_modifiers(self._hk_trigger_overlay[0]):
                        if self._on_toggle_trigger_overlay:
                            try: self._on_toggle_trigger_overlay()
                            except Exception: pass
                else:
                    # ── Combined mode (both triggers together) ────────────────
                    if vk == self._hk_trigger_up[1] and self._check_modifiers(self._hk_trigger_up[0]):
                        self._adjust_triggers(+_TRIGGER_STEP)
                    elif vk == self._hk_trigger_down[1] and self._check_modifiers(self._hk_trigger_down[0]):
                        self._adjust_triggers(-_TRIGGER_STEP)
                    elif vk == self._hk_toggle[1] and self._check_modifiers(self._hk_toggle[0]):
                        if self._on_toggle:
                            try: self._on_toggle()
                            except Exception: pass
                    elif vk == self._hk_center[1] and self._check_modifiers(self._hk_center[0]):
                        if self._on_center:
                            try: self._on_center()
                            except Exception: pass
                    elif vk == self._hk_switch_stick[1] and self._check_modifiers(self._hk_switch_stick[0]):
                        if self._on_switch_stick:
                            try: self._on_switch_stick()
                            except Exception: pass
                    elif vk == self._hk_reset_triggers[1] and self._check_modifiers(self._hk_reset_triggers[0]):
                        if self._on_reset_triggers:
                            try: self._on_reset_triggers()
                            except Exception: pass
                    elif vk == self._hk_crosshair[1] and self._check_modifiers(self._hk_crosshair[0]):
                        if self._on_toggle_crosshair:
                            try: self._on_toggle_crosshair()
                            except Exception: pass
                    elif vk == self._hk_trigger_overlay[1] and self._check_modifiers(self._hk_trigger_overlay[0]):
                        if self._on_toggle_trigger_overlay:
                            try: self._on_toggle_trigger_overlay()
                            except Exception: pass

            return ctypes.windll.user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        _hook_cb_ref = HOOKPROC(low_level_keyboard_proc)
        self._hook = ctypes.windll.user32.SetWindowsHookExW(
            _WH_KEYBOARD_LL,
            _hook_cb_ref,
            None,
            0
        )

        self._ready_event.set()

        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            ret = ctypes.windll.user32.PeekMessageW(
                ctypes.byref(msg), None, 0, 0, 1)
            if ret:
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)

        if self._hook:
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def _adjust_triggers(self, step: float):
        """Adjust both LT and RT by the same step."""
        with self._mapper._lock:
            lt = max(0.0, min(1.0, self._mapper.left_trigger  + step))
            rt = max(0.0, min(1.0, self._mapper.right_trigger + step))
            self._mapper.left_trigger  = lt
            self._mapper.right_trigger = rt
        if self._on_change:
            try: self._on_change(lt, rt)
            except Exception: pass

    def _adjust_lt(self, step: float):
        """Adjust LT only."""
        with self._mapper._lock:
            lt = max(0.0, min(1.0, self._mapper.left_trigger + step))
            # Reset RT if reset_opposite_trigger is enabled and LT is being increased
            if self._reset_opposite_trigger and step > 0 and lt > 0:
                rt = 0.0
                self._mapper.right_trigger = rt
            else:
                rt = self._mapper.right_trigger
            self._mapper.left_trigger = lt
        if self._on_change:
            try: self._on_change(lt, rt)
            except Exception: pass

    def _adjust_rt(self, step: float):
        """Adjust RT only."""
        with self._mapper._lock:
            # Reset LT if reset_opposite_trigger is enabled and RT is being increased
            if self._reset_opposite_trigger and step > 0:
                lt = 0.0
                self._mapper.left_trigger = lt
            else:
                lt = self._mapper.left_trigger
            rt = max(0.0, min(1.0, self._mapper.right_trigger + step))
            # Only reset if RT is actually being increased to above 0
            if self._reset_opposite_trigger and step > 0 and rt > 0:
                lt = 0.0
                self._mapper.left_trigger = lt
            self._mapper.right_trigger = rt
        if self._on_change:
            try: self._on_change(lt, rt)
            except Exception: pass


# ─────────────────────────────────────────────────────────────────────────────

class MouseJoystickMapper:
    """
    Polls the mouse cursor position and writes normalised values to the
    virtual game controller left stick (and optionally right stick for look).
    """

    POLL_HZ = 120

    def __init__(self):
        self.enabled = False
        self.sensitivity = 1.0
        self.deadzone    = 0.05
        self.use_right_stick = False

        # Trigger values controlled by TriggerHook (Ctrl+Scroll)
        self.left_trigger  = 0.0   # 0.0 – 1.0
        self.right_trigger = 0.0   # 0.0 – 1.0

        self._gamepad    = None
        self._thread     = None
        self._stop_event = threading.Event()
        self._lock       = threading.Lock()

        self._sw = 1920
        self._sh = 1080

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        if not VGAMEPAD_AVAILABLE:
            raise RuntimeError("vgamepad is not installed.\nRun:  pip install vgamepad")
        if self._thread and self._thread.is_alive():
            return
        self._gamepad = vg.VX360Gamepad()
        self._gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self._gamepad.update()
        time.sleep(0.05)
        self._gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self._gamepad.update()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._gamepad:
            try:
                self._gamepad.reset()
                self._gamepad.update()
            except Exception:
                pass
            self._gamepad = None

    # ── actions ──────────────────────────────────────────────────────────────

    def center(self):
        """Move physical cursor to screen centre, zero the virtual stick, and reset triggers."""
        sw, sh = self._get_screen_size()
        cx, cy = sw // 2, sh // 2
        ctypes.windll.user32.SetCursorPos(cx, cy)
        with self._lock:
            self.left_trigger  = 0.0
            self.right_trigger = 0.0
        if self._gamepad:
            try:
                if self.use_right_stick:
                    self._gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                else:
                    self._gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                self._gamepad.left_trigger_float(value_float=0.0)
                self._gamepad.right_trigger_float(value_float=0.0)
                self._gamepad.update()
            except Exception:
                pass

    # ── screen / cursor helpers ───────────────────────────────────────────────

    def _get_screen_size(self):
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    def _get_cursor_pos(self):
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _apply_deadzone(self, x: float, y: float) -> tuple:
        magnitude = math.sqrt(x * x + y * y)
        if magnitude < self.deadzone:
            return 0.0, 0.0
        scale = (magnitude - self.deadzone) / (1.0 - self.deadzone)
        scale = min(scale, 1.0)
        return (x / magnitude) * scale, (y / magnitude) * scale

    # ── poll loop ─────────────────────────────────────────────────────────────

    def _poll_loop(self):
        interval = 1.0 / self.POLL_HZ
        self._sw, self._sh = self._get_screen_size()
        while not self._stop_event.is_set():
            t0 = time.perf_counter()
            with self._lock:
                enabled     = self.enabled
                sensitivity = self.sensitivity
                deadzone    = self.deadzone
                right_stick = self.use_right_stick
                lt          = self.left_trigger
                rt          = self.right_trigger
            if self._gamepad:
                try:
                    self._gamepad.left_trigger_float(value_float=lt)
                    self._gamepad.right_trigger_float(value_float=rt)

                    if enabled:
                        cx2, cy2 = self._get_cursor_pos()
                        nx = (cx2 / self._sw) * 2.0 - 1.0
                        ny = -((cy2 / self._sh) * 2.0 - 1.0)
                        nx = max(-1.0, min(1.0, nx * sensitivity))
                        ny = max(-1.0, min(1.0, ny * sensitivity))
                        self.deadzone = deadzone
                        nx, ny = self._apply_deadzone(nx, ny)
                        if right_stick:
                            self._gamepad.right_joystick_float(x_value_float=nx, y_value_float=ny)
                        else:
                            self._gamepad.left_joystick_float(x_value_float=nx, y_value_float=ny)

                    self._gamepad.update()
                except Exception:
                    pass
            elapsed = time.perf_counter() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


# ─────────────────────────────────────────────────────────────────────────────
# Crosshair overlay
# ─────────────────────────────────────────────────────────────────────────────

class CrosshairOverlay:
    """Transparent overlay window that displays a white dot at screen center."""
    
    def __init__(self):
        self._window = None
        self._visible = False
    
    def show(self):
        """Show the crosshair overlay."""
        if self._window:
            return  # Already showing
        
        self._visible = True
        self._window = tk.Toplevel()
        self._window.title("Crosshair overlay")
        self._window.attributes("-topmost", True)
        self._window.attributes("-transparentcolor", "black")
        self._window.overrideredirect(True)  # Remove window decorations
        
        # Get screen size
        screen_width = self._window.winfo_screenwidth()
        screen_height = self._window.winfo_screenheight()
        
        # Dot size
        size = 10
        
        # Position window at screen center
        x = (screen_width - size) // 2
        y = (screen_height - size) // 2
        self._window.geometry(f"{size}x{size}+{x}+{y}")
        
        # Canvas with black background (will be transparent)
        canvas = tk.Canvas(self._window, width=size, height=size, 
                          bg="black", highlightthickness=0)
        canvas.pack()
        
        # Draw white dot (filled circle)
        canvas.create_oval(2, 2, size-2, size-2, fill="white", outline="")
        
        # Make window click-through (Windows only)
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            styles = styles | 0x80000 | 0x20  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, styles)
        except Exception:
            pass
    
    def hide(self):
        """Hide the crosshair overlay."""
        if self._window:
            self._window.destroy()
            self._window = None
        self._visible = False
    
    def is_visible(self):
        """Check if crosshair is currently visible."""
        return self._visible


class TriggerOverlay:
    """Transparent overlay window that displays LT/RT trigger bars at top left."""
    
    def __init__(self):
        self._window = None
        self._visible = False
        self._lt_canvas = None
        self._rt_canvas = None
        self._lt_bar = None
        self._rt_bar = None
        self._lt_outline = None
        self._rt_outline = None
        self._lt_label = None
        self._rt_label = None
        self._lt_text = None
        self._rt_text = None
        self._lt_value = 0.0
        self._rt_value = 0.0
    
    def show(self):
        """Show the trigger overlay."""
        if self._window:
            return  # Already showing
        
        self._visible = True
        self._window = tk.Toplevel()
        self._window.title("Triggers")
        self._window.attributes("-topmost", True)
        self._window.attributes("-transparentcolor", "black")
        self._window.overrideredirect(True)  # Remove window decorations
        
        # Overlay dimensions
        label_width = 30
        bar_width = 260
        value_width = 40
        bar_height = 16
        spacing = 8
        margin = 20
        total_width = label_width + bar_width + value_width
        total_height = (bar_height * 2) + spacing
        
        # Position at top left
        x = margin
        y = margin
        self._window.geometry(f"{total_width}x{total_height}+{x}+{y}")
        self._window.config(bg="black")
        
        # LT bar (top)
        lt_frame = tk.Frame(self._window, bg="black")
        lt_frame.pack(pady=(0, spacing))
        
        # LT label
        lt_label_canvas = tk.Canvas(lt_frame, width=label_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        lt_label_canvas.pack(side="left")
        self._lt_label = lt_label_canvas.create_text(
            5, bar_height // 2, text="LT",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        # LT bar
        self._lt_canvas = tk.Canvas(lt_frame, width=bar_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        self._lt_canvas.pack(side="left")
        
        # Draw LT bar outline (white border)
        self._lt_outline = self._lt_canvas.create_rectangle(
            0, 0, bar_width, bar_height, fill="", outline="white", width=2
        )
        # Draw LT bar fill
        self._lt_bar = self._lt_canvas.create_rectangle(
            2, 2, 2, bar_height-2, fill="white", outline=""
        )
        
        # LT value canvas (separate canvas for value text)
        lt_value_canvas = tk.Canvas(lt_frame, width=value_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        lt_value_canvas.pack(side="left")
        self._lt_text = lt_value_canvas.create_text(
            5, bar_height // 2, text="0",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        # RT bar (bottom)
        rt_frame = tk.Frame(self._window, bg="black")
        rt_frame.pack()
        
        # RT label
        rt_label_canvas = tk.Canvas(rt_frame, width=label_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        rt_label_canvas.pack(side="left")
        self._rt_label = rt_label_canvas.create_text(
            5, bar_height // 2, text="RT",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        # RT bar
        self._rt_canvas = tk.Canvas(rt_frame, width=bar_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        self._rt_canvas.pack(side="left")
        
        # Draw RT bar outline (white border)
        self._rt_outline = self._rt_canvas.create_rectangle(
            0, 0, bar_width, bar_height, fill="", outline="white", width=2
        )
        # Draw RT bar fill
        self._rt_bar = self._rt_canvas.create_rectangle(
            2, 2, 2, bar_height-2, fill="white", outline=""
        )
        
        # RT value canvas (separate canvas for value text)
        rt_value_canvas = tk.Canvas(rt_frame, width=value_width, height=bar_height,
                                    bg="black", highlightthickness=0)
        rt_value_canvas.pack(side="left")
        self._rt_text = rt_value_canvas.create_text(
            5, bar_height // 2, text="0",
            fill="white", anchor="w", font=("Arial", 11, "bold")
        )
        
        # Store value canvas references
        self._lt_value_canvas = lt_value_canvas
        self._rt_value_canvas = rt_value_canvas
        
        # Update with current values
        self.update_values(self._lt_value, self._rt_value)
        
        # Make window click-through (Windows only)
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            styles = styles | 0x80000 | 0x20  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, styles)
        except Exception:
            pass
    
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
        
        # Update LT bar (account for border)
        lt_width = int((bar_width - border * 2) * lt) + border
        self._lt_canvas.coords(self._lt_bar, border, border, lt_width, bar_height - border)
        if hasattr(self, '_lt_value_canvas'):
            self._lt_value_canvas.itemconfig(self._lt_text, text=str(int(lt * 100)))
        
        # Update RT bar (account for border)
        rt_width = int((bar_width - border * 2) * rt) + border
        self._rt_canvas.coords(self._rt_bar, border, border, rt_width, bar_height - border)
        if hasattr(self, '_rt_value_canvas'):
            self._rt_value_canvas.itemconfig(self._rt_text, text=str(int(rt * 100)))
    
    def is_visible(self):
        """Check if trigger overlay is currently visible."""
        return self._visible


# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    # Dark theme colors
    DARK_ACCENT   = "#5865F2"
    DARK_BG       = "#1e1f2e"
    DARK_BG2      = "#2a2b3d"
    DARK_FG       = "#e0e0f0"
    DARK_FG_DIM   = "#8888aa"
    DARK_GREEN    = "#43b581"
    DARK_RED      = "#ed4245"
    DARK_YELLOW   = "#faa61a"
    
    # Light theme colors
    LIGHT_ACCENT  = "#5865F2"
    LIGHT_BG      = "#ffffff"
    LIGHT_BG2     = "#f0f0f0"
    LIGHT_FG      = "#2e2e2e"
    LIGHT_FG_DIM  = "#666666"
    LIGHT_GREEN   = "#2d8659"
    LIGHT_RED     = "#d32f2f"
    LIGHT_YELLOW  = "#f57c00"
    
    FONT     = ("Segoe UI", 10)
    FONT_BIG = ("Segoe UI", 13, "bold")
    FONT_MONO= ("Consolas", 10)

    def __init__(self, mapper: MouseJoystickMapper, hotkeys,
                 trigger_hook: TriggerHook, cfg: dict):
        super().__init__()
        self.mapper       = mapper
        self.trigger_hook = trigger_hook
        self.cfg          = cfg
        self.crosshair    = CrosshairOverlay()
        self.trigger_overlay = TriggerOverlay()

        # Apply theme
        self._current_theme = cfg.get("theme", "dark")
        self._apply_theme()

        self.title("vCTRL — Virtual Controller")
        self.resizable(False, False)
        self.minsize(500, 100)
        self.configure(bg=self.BG)
        
        # Set window icon if available
        self._set_icon()

        self._enabled_var = tk.BooleanVar(value=False)
        self._sens_var    = tk.DoubleVar(value=cfg["sensitivity"])
        self._dz_var      = tk.DoubleVar(value=cfg["deadzone"])
        self._stick_var   = tk.StringVar(value=cfg["stick"])

        # Hotkey combo strings
        self._hk_toggle_var = tk.StringVar(value=cfg.get("hotkey_toggle", "capslock"))
        self._hk_center_var = tk.StringVar(value=cfg.get("hotkey_center", "`"))
        self._hk_trigger_up_var   = tk.StringVar(value=cfg.get("hotkey_trigger_up",   "w"))
        self._hk_trigger_down_var = tk.StringVar(value=cfg.get("hotkey_trigger_down", "s"))
        self._hk_lt_up_var        = tk.StringVar(value=cfg.get("hotkey_lt_up",   "q"))
        self._hk_lt_down_var      = tk.StringVar(value=cfg.get("hotkey_lt_down",  "a"))
        self._hk_rt_up_var        = tk.StringVar(value=cfg.get("hotkey_rt_up",   "e"))
        self._hk_rt_down_var      = tk.StringVar(value=cfg.get("hotkey_rt_down",  "d"))
        self._hk_switch_stick_var       = tk.StringVar(value=cfg.get("hotkey_switch_stick",    "alt+x"))
        self._hk_reset_triggers_var     = tk.StringVar(value=cfg.get("hotkey_reset_triggers",  "alt+t"))
        self._hk_crosshair_var          = tk.StringVar(value=cfg.get("hotkey_crosshair",       "f1"))
        self._hk_trigger_overlay_var    = tk.StringVar(value=cfg.get("hotkey_trigger_overlay", "f2"))

        # Listening state
        self._listening_for = None

        # Overlay and trigger state vars
        self._crosshair_var = tk.BooleanVar(value=cfg.get("crosshair", False))
        self._trigger_overlay_var = tk.BooleanVar(value=cfg.get("trigger_overlay", False))
        self._sep_triggers_var = tk.BooleanVar(value=cfg.get("separate_triggers", False))
        self._reset_opposite_trigger_var = tk.BooleanVar(value=cfg.get("reset_opposite_trigger", False))

        # Trigger display vars
        self._lt_var = tk.IntVar(value=0)
        self._rt_var = tk.IntVar(value=0)

        self._build_ui()
        self._apply_all_settings()

        self._tray_icon = None
        if TRAY_AVAILABLE:
            self._start_tray()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.update_idletasks()
        self._center_window()


    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Permanent header ───────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=self.BG)
        hdr.pack(fill="x", padx=16, pady=4)
        tk.Label(hdr, text="vCTRL", font=self.FONT_BIG,
                 bg=self.BG, fg=self.ACCENT).pack(side="left")

        # Theme selector on right
        theme_frame = tk.Frame(hdr, bg=self.BG)
        theme_frame.pack(side="right")
        tk.Label(theme_frame, text="Theme:", font=self.FONT,
                 bg=self.BG, fg=self.FG).pack(side="left", padx=(0, 8))

        self._theme_var = tk.StringVar(value=self._current_theme.title())
        for theme in ("Dark", "Light"):
            tk.Radiobutton(
                theme_frame, text=theme, variable=self._theme_var, value=theme,
                font=self.FONT, bg=self.BG, fg=self.FG,
                selectcolor=self.ACCENT, activebackground=self.BG,
                relief="flat", cursor="hand2",
                command=self._on_theme_change,
            ).pack(side="left", padx=2)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(4, 0))

        # ── Tab bar ────────────────────────────────────────────────────────────
        # Preserve active tab across theme changes
        if not hasattr(self, '_active_tab'):
            self._active_tab = "overview"

        tab_bar = tk.Frame(self, bg=self.BG)
        tab_bar.pack(fill="x", padx=16, pady=(6, 6))

        self._tab_overview_lbl = tk.Label(
            tab_bar, text="Overview", font=("Segoe UI", 10, "bold"),
            bg=self.BG, cursor="hand2"
        )
        self._tab_overview_lbl.pack(side="left", padx=(0, 16))
        self._tab_overview_lbl.bind("<Button-1>", lambda e: self._switch_tab("overview"))

        self._tab_options_lbl = tk.Label(
            tab_bar, text="Options", font=("Segoe UI", 10, "bold"),
            bg=self.BG, cursor="hand2"
        )
        self._tab_options_lbl.pack(side="left")
        self._tab_options_lbl.bind("<Button-1>", lambda e: self._switch_tab("options"))

        self._update_tab_labels()

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(0, 0))

        # ── Permanent status banner ────────────────────────────────────────────
        self._status_frame = tk.Frame(self, bg=self.BG2, pady=6)
        self._status_frame.pack(fill="x", padx=16, pady=0)
        self._status_label = tk.Label(
            self._status_frame, text="Initialising…",
            font=self.FONT, bg=self.BG2, fg=self.FG_DIM, anchor="center")
        self._status_label.pack()

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(0, 0))

        # ── Tab content frame ──────────────────────────────────────────────────
        self._tab_frame = tk.Frame(self, bg=self.BG)
        self._tab_frame.pack(fill="both", expand=True)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = tk.Label(
            self, text="—",
            font=self.FONT_BIG,
            bg=self.BG, fg=self.ACCENT,
            cursor="hand2"
        )
        footer.pack(pady=(0, 8))
        footer.bind("<Button-1>", lambda e: self._open_website())

        # ── Start services ─────────────────────────────────────────────────────
        if VGAMEPAD_AVAILABLE:
            try:
                self.mapper.start()
                self._set_status("Virtual controller connected", ok=True)
            except Exception as e:
                self._set_status(str(e), ok=False)
        else:
            self._set_status("vgamepad not installed — run: pip install vgamepad", ok=False)

        # Start trigger hook and wire callbacks
        self.trigger_hook._on_change = self._on_trigger_change
        self.trigger_hook._on_toggle = self._toggle_enabled_threadsafe
        self.trigger_hook._on_center = self._do_center_threadsafe
        self.trigger_hook._on_switch_stick = self._switch_stick_threadsafe
        self.trigger_hook._on_reset_triggers = self._reset_triggers_threadsafe
        self.trigger_hook._on_toggle_crosshair = self._toggle_crosshair_threadsafe
        self.trigger_hook._on_toggle_trigger_overlay = self._toggle_trigger_overlay_threadsafe
        self.trigger_hook.start()

        # Set title bar color after window is fully created
        self.after(100, self._set_title_bar_color)

        # Build the active tab
        self._switch_tab(self._active_tab)

        # Start preview update loop (only once — survives tab and theme switches)
        if not getattr(self, '_preview_running', False):
            self._preview_running = True
            self._update_preview()

    def _update_tab_labels(self):
        """Update tab label colours to reflect the active tab."""
        if self._active_tab == "overview":
            self._tab_overview_lbl.config(fg=self.ACCENT)
            self._tab_options_lbl.config(fg=self.FG)
        else:
            self._tab_overview_lbl.config(fg=self.FG)
            self._tab_options_lbl.config(fg=self.ACCENT)

    def _switch_tab(self, tab_name: str):
        """Switch active tab, clear the content frame and rebuild."""
        self._active_tab = tab_name
        self._update_tab_labels()

        # Cancel any in-progress hotkey listening
        if getattr(self, '_listening_for', None):
            self._cancel_listening()

        # Destroy previous tab widgets
        for widget in self._tab_frame.winfo_children():
            widget.destroy()

        # Reset tracked hotkey entry widgets
        self._hk_entry_widgets = []

        if tab_name == "overview":
            self._build_overview()
        else:
            self._build_options()

    def _build_overview(self):
        """Build the Overview tab: joystick preview, toggle/center, trigger bars."""
        p = self._tab_frame

        # ── Cursor Section ────────────────────────────────────────────────────
        cursor_hdr = tk.Frame(p, bg=self.BG)
        cursor_hdr.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(cursor_hdr, text="Cursor", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")

        # Stick selector beside Cursor title
        stick_frame = tk.Frame(cursor_hdr, bg=self.BG)
        stick_frame.pack(side="right")
        tk.Label(stick_frame, text="Stick:", font=self.FONT,
                 bg=self.BG, fg=self.FG).pack(side="left", padx=(0, 8))
        for label in ("Left", "Right"):
            tk.Radiobutton(
                stick_frame, text=label, variable=self._stick_var, value=label,
                font=self.FONT, bg=self.BG, fg=self.FG,
                selectcolor=self.ACCENT, activebackground=self.BG,
                relief="flat", cursor="hand2",
                command=self._on_stick_change).pack(side="left", padx=4)

        # Joystick canvas pair
        canvas_frame = tk.Frame(p, bg=self.BG)
        canvas_frame.pack(pady=(0, 4))

        left_preview = tk.Frame(canvas_frame, bg=self.BG)
        left_preview.pack(side="left", padx=4)
        tk.Label(left_preview, text="L", font=("Segoe UI", 9, "bold"),
                 bg=self.BG, fg=self.FG).pack()
        self._canvas_left = tk.Canvas(left_preview, width=100, height=100,
                                      bg=self.BG2, highlightthickness=1,
                                      highlightbackground=self.FG_DIM)
        self._canvas_left.pack()

        right_preview = tk.Frame(canvas_frame, bg=self.BG)
        right_preview.pack(side="left", padx=4)
        tk.Label(right_preview, text="R", font=("Segoe UI", 9, "bold"),
                 bg=self.BG, fg=self.FG).pack()
        self._canvas_right = tk.Canvas(right_preview, width=100, height=100,
                                       bg=self.BG2, highlightthickness=1,
                                       highlightbackground=self.FG_DIM)
        self._canvas_right.pack()

        self._draw_joystick_preview(0.0, 0.0)

        # Cursor position readout
        pos_frame = tk.Frame(p, bg=self.BG)
        pos_frame.pack(fill="x", padx=16, pady=(0, 4))
        self._pos_label = tk.Label(pos_frame, text="X: +0.000   Y: +0.000",
                                   font=self.FONT_MONO, bg=self.BG, fg=self.FG)
        self._pos_label.pack()

        # Toggle / Center buttons
        ctrl = tk.Frame(p, bg=self.BG)
        ctrl.pack(pady=(0, 4))

        self._toggle_btn = tk.Button(
            ctrl, text="▶",
            font=("Segoe UI", 10, "bold"),
            bg=self.BG2, fg=self.FG,
            activebackground=self.ACCENT, activeforeground="white",
            relief="flat", padx=32, pady=4, cursor="hand2",
            command=self._toggle_enabled)
        self._toggle_btn.pack(side="left")
        # Restore button state if already active
        if self._enabled_var.get():
            self._toggle_btn.config(text="■", bg=self.ACCENT, fg="white")

        self._center_btn = tk.Button(
            ctrl, text="Center",
            font=("Segoe UI", 10),
            bg=self.BG2, fg=self.FG,
            activebackground=self.BG2, activeforeground=self.FG,
            relief="flat", padx=20, pady=4, cursor="hand2",
            command=self._do_center)
        self._center_btn.pack(side="left", padx=(8, 0))

        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=16, pady=6)

        # ── Triggers Section ──────────────────────────────────────────────────
        trig_hdr = tk.Frame(p, bg=self.BG)
        trig_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(trig_hdr, text="Triggers", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")

        self._lt_bar = self._build_trigger_bar(p, "LT", self._lt_var)
        self._rt_bar = self._build_trigger_bar(p, "RT", self._rt_var)

        # Reset triggers button
        trig_reset_row = tk.Frame(p, bg=self.BG)
        trig_reset_row.pack(pady=(2, 8))
        tk.Button(
            trig_reset_row, text="Reset Triggers",
            font=("Segoe UI", 10),
            bg=self.BG2, fg=self.FG,
            activebackground=self.BG2, activeforeground=self.FG,
            relief="flat", width=20, pady=4, cursor="hand2",
            command=self._reset_triggers,
        ).pack()

    def _build_options(self):
        """Build the Options tab: sliders, hotkeys, overlay settings."""
        p = self._tab_frame

        # ── Cursor Section ────────────────────────────────────────────────────
        cursor_hdr = tk.Frame(p, bg=self.BG)
        cursor_hdr.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(cursor_hdr, text="Cursor", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")

        self._build_slider(p, "Sensitivity", self._sens_var,
                           0.1, 3.0, 0.05, lambda v: f"{v:.2f}x",
                           self._on_sens_change)
        self._build_slider(p, "Dead-zone", self._dz_var,
                           0.0, 0.5, 0.01, lambda v: f"{int(v*100)}%",
                           self._on_dz_change)

        # Cursor hotkeys sub-header
        hk_hdr = tk.Frame(p, bg=self.BG)
        hk_hdr.pack(fill="x", padx=16, pady=(8, 2))
        tk.Label(hk_hdr, text="Hotkeys", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")
        tk.Label(hk_hdr, text="", width=6, bg=self.BG).pack(side="left")
        tk.Label(hk_hdr, text="(click to customize)",
                 font=self.FONT, bg=self.BG, fg=self.FG_DIM, anchor="w").pack(side="left")

        self._hk_toggle_entry = self._build_hotkey_row(p, "Toggle", self._hk_toggle_var, "toggle")
        self._hk_center_entry = self._build_hotkey_row(p, "Center", self._hk_center_var, "center")
        self._hk_switch_stick_entry = self._build_hotkey_row(p, "Switch Stick", self._hk_switch_stick_var, "switch_stick")

        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=16, pady=6)

        # ── Triggers Section ──────────────────────────────────────────────────
        trig_hdr = tk.Frame(p, bg=self.BG)
        trig_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(trig_hdr, text="Triggers", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")

        # Separate Triggers checkbox
        sep_trig_frame = tk.Frame(p, bg=self.BG)
        sep_trig_frame.pack(fill="x", padx=16, pady=(0, 4))
        tk.Checkbutton(
            sep_trig_frame, text="Separate Triggers",
            variable=self._sep_triggers_var,
            font=self.FONT, bg=self.BG, fg=self.FG,
            selectcolor=self.ACCENT, activebackground=self.BG,
            relief="flat", cursor="hand2",
            command=self._on_separate_triggers_change
        ).pack(side="left")
        
        # Reset Opposite Trigger checkbox (only shown in separate mode)
        if self._sep_triggers_var.get():
            tk.Checkbutton(
                sep_trig_frame, text="Reset Opposite Trigger",
                variable=self._reset_opposite_trigger_var,
                font=self.FONT, bg=self.BG, fg=self.FG,
                selectcolor=self.ACCENT, activebackground=self.BG,
                relief="flat", cursor="hand2",
                command=self._on_reset_opposite_trigger_change
            ).pack(side="left", padx=(16, 0))

        # Trigger hotkeys sub-header
        hk_hdr2 = tk.Frame(p, bg=self.BG)
        hk_hdr2.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(hk_hdr2, text="Hotkeys", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")
        tk.Label(hk_hdr2, text="", width=6, bg=self.BG).pack(side="left")
        tk.Label(hk_hdr2, text="(click to customize)",
                 font=self.FONT, bg=self.BG, fg=self.FG_DIM, anchor="w").pack(side="left")

        if self._sep_triggers_var.get():
            # Per-trigger rows
            self._hk_lt_up_entry   = self._build_hotkey_row(p, "LT +", self._hk_lt_up_var,   "lt_up")
            self._hk_lt_down_entry = self._build_hotkey_row(p, "LT −", self._hk_lt_down_var, "lt_down")
            self._hk_rt_up_entry   = self._build_hotkey_row(p, "RT +", self._hk_rt_up_var,   "rt_up")
            self._hk_rt_down_entry = self._build_hotkey_row(p, "RT −", self._hk_rt_down_var, "rt_down")
        else:
            # Combined rows
            self._hk_trigger_up_entry   = self._build_hotkey_row(p, "Trigger +", self._hk_trigger_up_var,   "trigger_up")
            self._hk_trigger_down_entry = self._build_hotkey_row(p, "Trigger −", self._hk_trigger_down_var, "trigger_down")
        self._hk_reset_triggers_entry = self._build_hotkey_row(p, "Reset Triggers", self._hk_reset_triggers_var, "reset_triggers")

        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=16, pady=6)

        # ── Overlay Section ───────────────────────────────────────────────────
        overlay_hdr = tk.Frame(p, bg=self.BG)
        overlay_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(overlay_hdr, text="Overlay", font=("Segoe UI", 10, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")
        # Overlay enable checkboxes
        overlay_toggles = tk.Frame(p, bg=self.BG)
        overlay_toggles.pack(fill="x", padx=16, pady=(0, 4))
        tk.Checkbutton(
            overlay_toggles, text="Crosshair",
            variable=self._crosshair_var,
            font=self.FONT, bg=self.BG, fg=self.FG,
            selectcolor=self.ACCENT, activebackground=self.BG,
            relief="flat", cursor="hand2",
            command=self._on_crosshair_change
        ).pack(side="left", padx=(0, 16))
        tk.Checkbutton(
            overlay_toggles, text="Triggers",
            variable=self._trigger_overlay_var,
            font=self.FONT, bg=self.BG, fg=self.FG,
            selectcolor=self.ACCENT, activebackground=self.BG,
            relief="flat", cursor="hand2",
            command=self._on_trigger_overlay_change
        ).pack(side="left")

        self._hk_crosshair_entry = self._build_hotkey_row(p, "Crosshair", self._hk_crosshair_var, "crosshair")
        self._hk_trigger_overlay_entry = self._build_hotkey_row(p, "Trigger overlay", self._hk_trigger_overlay_var, "trigger_overlay")

        # Save Settings button
        save_btn_frame = tk.Frame(p, bg=self.BG)
        save_btn_frame.pack(pady=(12, 8))
        tk.Button(
            save_btn_frame, text="Save Settings",
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT, fg="white",
            activebackground=self.GREEN, activeforeground="white",
            relief="flat", width=20, pady=6, cursor="hand2",
            command=self._on_save_button_click
        ).pack()

        # Bottom padding
        tk.Frame(p, bg=self.BG, height=8).pack()


    # ── Hotkey row builder ───────────────────────────────────────────────────

    def _build_hotkey_row(self, parent, label: str, var: tk.StringVar, hk_name: str, readonly: bool = False) -> tk.Label:
        """Build a labelled hotkey row inside `parent`."""
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill="x", padx=16, pady=3)

        # Label on left with fixed width to match sliders and triggers
        tk.Label(row, text=label, font=self.FONT,
                 bg=self.BG, fg=self.FG, width=14, anchor="w").pack(side="left")

        # Clear button on right with fixed width
        if not readonly:
            clear_btn = tk.Button(
                row, text="\u2715", font=("Segoe UI", 9),
                bg=self.BG2, fg=self.RED,
                activebackground=self.BG2, activeforeground=self.RED,
                relief="flat", width=6, pady=2, cursor="hand2",
                command=lambda: self._clear_hotkey(hk_name, var)
            )
            clear_btn.pack(side="right")

        # Hotkey field fills the space between
        entry_frame = tk.Frame(row, bg=self.BG2, relief="flat", bd=1, highlightthickness=1,
                               highlightbackground=self.BG2)
        entry_frame.pack(side="left", fill="x", expand=True, padx=(4, 8))

        entry_label = tk.Label(
            entry_frame, textvariable=var,
            font=self.FONT_MONO,
            bg=self.BG2, fg=self.FG,
            anchor="w", padx=4, pady=4,
            cursor="hand2" if not readonly else "arrow"
        )
        entry_label.pack(fill="x")

        if not readonly:
            entry_label.bind("<Button-1>", lambda e: self._start_listening(hk_name, entry_label, var))

        # Track this widget so _stop_listening can reset its colour
        if not hasattr(self, '_hk_entry_widgets'):
            self._hk_entry_widgets = []
        self._hk_entry_widgets.append(entry_label)

        return entry_label

    # ── Hotkey recording ─────────────────────────────────────────────────────

    def _start_listening(self, hk_name: str, entry_label: tk.Label, var: tk.StringVar):
        """Put the entry in listening mode — next key combo will be captured."""
        if self._listening_for == hk_name:
            self._stop_listening()
            return
        self._stop_listening()
        self._listening_for = hk_name
        
        # Store the original value to restore on cancel
        if not hasattr(self, '_original_hotkey_values'):
            self._original_hotkey_values = {}
        self._original_hotkey_values[hk_name] = var.get()
        
        var.set("Press a key combo…")
        entry_label.config(fg=self.YELLOW)
        # Grab all keyboard events on the root window
        self.bind("<KeyPress>",  self._on_key_press_listen)
        self.bind("<FocusOut>",  lambda e: self._cancel_listening())
        self.focus_force()
        
        # Start 15-second timeout
        if hasattr(self, '_timeout_id') and self._timeout_id:
            self.after_cancel(self._timeout_id)
        self._timeout_id = self.after(15000, self._timeout_listening)  # 15 seconds

    def _stop_listening(self):
        """Stop listening and restore normal colors."""
        # Cancel timeout if exists
        if hasattr(self, '_timeout_id') and self._timeout_id:
            self.after_cancel(self._timeout_id)
            self._timeout_id = None

        self._listening_for = None
        self.unbind("<KeyPress>")
        self.unbind("<FocusOut>")
        # Restore colours for all currently visible hotkey entry widgets
        for entry_label in getattr(self, '_hk_entry_widgets', []):
            try:
                entry_label.config(fg=self.FG)
            except Exception:
                pass
    
    def _timeout_listening(self):
        """Called after 15 seconds of no input - revert to original value."""
        if self._listening_for:
            self._cancel_listening()

    def _cancel_listening(self):
        """Cancel listening and restore the original value."""
        if self._listening_for and hasattr(self, '_original_hotkey_values'):
            hk_name = self._listening_for
            _hk_var_map = {
                "toggle":          self._hk_toggle_var,
                "center":          self._hk_center_var,
                "switch_stick":    self._hk_switch_stick_var,
                "trigger_up":      self._hk_trigger_up_var,
                "trigger_down":    self._hk_trigger_down_var,
                "lt_up":           self._hk_lt_up_var,
                "lt_down":         self._hk_lt_down_var,
                "rt_up":           self._hk_rt_up_var,
                "rt_down":         self._hk_rt_down_var,
                "reset_triggers":  self._hk_reset_triggers_var,
                "crosshair":       self._hk_crosshair_var,
                "trigger_overlay": self._hk_trigger_overlay_var,
            }
            if hk_name in _hk_var_map and hk_name in self._original_hotkey_values:
                _hk_var_map[hk_name].set(self._original_hotkey_values[hk_name])
        self._stop_listening()

    def _on_key_press_listen(self, event: tk.Event):
        keysym = event.keysym.lower()

        # Escape cancels
        if keysym == "escape":
            self._cancel_listening()
            return

        # Collect modifiers - be more strict about detection
        mods = []
        state = event.state
        # Tkinter state bits: Shift=1, Control=4, Alt/Mod1=0x20000 or 8
        # Only add modifiers if they are actually held down
        if state & 0x1:
            mods.append("shift")
        if state & 0x4:
            mods.append("ctrl")
        # Alt is tricky - check both Mod1 flags, but exclude system key events
        # 0x20000 is the reliable Alt flag, 0x8 can be spurious
        if state & 0x20000:
            mods.append("alt")

        # Ignore if the pressed key IS a modifier alone
        if keysym in ("shift_l","shift_r","control_l","control_r",
                      "alt_l","alt_r","super_l","super_r",
                      "caps_lock","num_lock","scroll_lock"):
            return

        # Normalise the key name
        key = keysym.replace("_l","").replace("_r","")
        if len(key) == 1 and key.isalpha():
            key = key.lower()

        parts = mods + [key]
        combo = "+".join(parts)

        hk_name = self._listening_for

        # Cancel timeout since we got input
        if hasattr(self, '_timeout_id') and self._timeout_id:
            self.after_cancel(self._timeout_id)
            self._timeout_id = None

        self._stop_listening()

        # Set the new hotkey
        _hk_var_map = {
            "toggle":         self._hk_toggle_var,
            "center":         self._hk_center_var,
            "switch_stick":   self._hk_switch_stick_var,
            "trigger_up":     self._hk_trigger_up_var,
            "trigger_down":   self._hk_trigger_down_var,
            "lt_up":          self._hk_lt_up_var,
            "lt_down":        self._hk_lt_down_var,
            "rt_up":          self._hk_rt_up_var,
            "rt_down":        self._hk_rt_down_var,
            "reset_triggers": self._hk_reset_triggers_var,
            "crosshair":      self._hk_crosshair_var,
            "trigger_overlay":self._hk_trigger_overlay_var,
        }
        if hk_name in _hk_var_map:
            _hk_var_map[hk_name].set(combo)
        
        # Apply the new hotkeys to the hook
        self._apply_hotkeys()

    def _clear_hotkey(self, hk_name: str, var: tk.StringVar):
        """Clear a hotkey binding."""
        var.set("")
        self._apply_hotkeys()

    # ── Hotkey registration helpers ──────────────────────────────────────────

    def _toggle_enabled_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._toggle_enabled)

    def _do_center_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._do_center)

    def _toggle_crosshair_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._toggle_crosshair)

    def _toggle_trigger_overlay_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._toggle_trigger_overlay)


    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Set color attributes based on current theme"""
        if self._current_theme == "dark":
            self.ACCENT = self.DARK_ACCENT
            self.BG = self.DARK_BG
            self.BG2 = self.DARK_BG2
            self.FG = self.DARK_FG
            self.FG_DIM = self.DARK_FG_DIM
            self.GREEN = self.DARK_GREEN
            self.RED = self.DARK_RED
            self.YELLOW = self.DARK_YELLOW
        else:
            self.ACCENT = self.LIGHT_ACCENT
            self.BG = self.LIGHT_BG
            self.BG2 = self.LIGHT_BG2
            self.FG = self.LIGHT_FG
            self.FG_DIM = self.LIGHT_FG_DIM
            self.GREEN = self.LIGHT_GREEN
            self.RED = self.LIGHT_RED
            self.YELLOW = self.LIGHT_YELLOW

    def _on_theme_change(self):
        """Switch theme and rebuild UI"""
        new_theme = self._theme_var.get().lower()
        if new_theme == self._current_theme:
            return
        
        self._current_theme = new_theme
        self.cfg["theme"] = new_theme
        
        # Destroy all widgets and rebuild
        for widget in self.winfo_children():
            widget.destroy()
        
        self._apply_theme()
        self.configure(bg=self.BG)
        
        # Apply title bar color based on theme
        self._set_title_bar_color()
        
        # Rebuild UI
        self._build_ui()

    def _set_title_bar_color(self):
        """Set title bar to dark or light based on current theme."""
        try:
            HWND = ctypes.windll.user32.GetParent(self.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            # 1 = dark mode, 0 = light mode
            value = ctypes.c_int(1 if self._current_theme == "dark" else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                HWND, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _build_trigger_bar(self, parent, label: str, var: tk.IntVar) -> ttk.Progressbar:
        """Build a labelled trigger progress bar inside `parent`."""
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill="x", padx=16, pady=3)
        
        # Label on left with fixed width to match sliders and hotkeys
        tk.Label(row, text=label, font=self.FONT,
                 bg=self.BG, fg=self.FG, width=14, anchor="w").pack(side="left")
        
        # Percentage label on right with fixed width
        pct_lbl = tk.Label(row, text="  0%", font=self.FONT_MONO,
                           bg=self.BG, fg=self.ACCENT, width=6, anchor="e")
        pct_lbl.pack(side="right")
        
        # Progress bar fills the space between
        style_name = f"{label}.Horizontal.TProgressbar"
        style = ttk.Style()
        style.theme_use("default")
        style.configure(style_name,
                        troughcolor=self.BG2,
                        background=self.ACCENT,
                        thickness=14)
        bar = ttk.Progressbar(row, style=style_name,
                              variable=var, maximum=100,
                              orient="horizontal")
        bar.pack(side="left", fill="x", expand=True, padx=(4, 8))
        
        # Store label reference keyed by var so we can update it
        setattr(self, f"_{'lt' if label == 'LT' else 'rt'}_pct_label", pct_lbl)
        return bar

    def _on_trigger_change(self, lt: float, rt: float):
        """Called from TriggerHook thread — must post to Tk thread."""
        self.after(0, lambda: self._refresh_trigger_ui(lt, rt))

    def _refresh_trigger_ui(self, lt: float, rt: float):
        self._lt_var.set(int(lt * 100))
        self._rt_var.set(int(rt * 100))
        # Labels only exist when the Overview tab is active
        try:
            self._lt_pct_label.config(text=f"{int(lt*100):3d}%")
            self._rt_pct_label.config(text=f"{int(rt*100):3d}%")
        except Exception:
            pass
        # Update trigger overlay if visible
        self.trigger_overlay.update_values(lt, rt)

    def _reset_triggers(self):
        with self.mapper._lock:
            self.mapper.left_trigger  = 0.0
            self.mapper.right_trigger = 0.0
        self._refresh_trigger_ui(0.0, 0.0)
        self._set_status("Triggers reset", ok=True)

    def _reset_triggers_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._reset_triggers)

    # ── Slider builder ────────────────────────────────────────────────────────

    def _build_slider(self, parent, label, var, from_, to, resolution, fmt, callback):
        """Build a labelled slider inside `parent`."""
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill="x", padx=16, pady=4)
        
        # Label on left with fixed width
        tk.Label(row, text=label, font=self.FONT,
                 bg=self.BG, fg=self.FG, width=14, anchor="w").pack(side="left")
        
        # Value label on right with fixed width
        value_label = tk.Label(row, text=fmt(var.get()), font=self.FONT_MONO,
                               bg=self.BG, fg=self.ACCENT, width=6, anchor="e")
        value_label.pack(side="right")
        
        def on_change(val):
            value_label.config(text=fmt(float(val)))
            callback(float(val))
        
        # Slider fills the space between label and value
        scale = tk.Scale(
            row, variable=var, from_=from_, to=to,
            resolution=resolution, orient="horizontal",
            showvalue=False, command=on_change,
            bg=self.BG, fg=self.FG, troughcolor=self.BG2,
            activebackground=self.ACCENT, highlightthickness=0,
            sliderlength=16)
        scale.pack(side="left", fill="x", expand=True, padx=(4, 8))

    # ── Live preview ──────────────────────────────────────────────────────────

    def _update_preview(self):
        try:
            cx, cy = self.mapper._get_cursor_pos()
            sw, sh = self.mapper._sw, self.mapper._sh
            nx = (cx / sw) * 2.0 - 1.0
            ny = -((cy / sh) * 2.0 - 1.0)
            nx = max(-1.0, min(1.0, nx * self._sens_var.get()))
            ny = max(-1.0, min(1.0, ny * self._sens_var.get()))
            nx, ny = self.mapper._apply_deadzone(nx, ny)
            self._pos_label.config(text=f"X: {nx:+.3f}   Y: {ny:+.3f}")
            self._draw_joystick_preview(nx, ny)
        except Exception:
            pass
        self.after(33, self._update_preview)

    def _draw_joystick_preview(self, nx: float, ny: float):
        """Draw joystick position on both L and R previews, with active one highlighted."""
        use_right = self.mapper.use_right_stick
        
        # Draw left stick
        self._draw_single_stick(self._canvas_left, nx if not use_right else 0.0, 
                               ny if not use_right else 0.0, active=not use_right)
        
        # Draw right stick
        self._draw_single_stick(self._canvas_right, nx if use_right else 0.0, 
                               ny if use_right else 0.0, active=use_right)
    
    def _draw_single_stick(self, canvas, nx: float, ny: float, active: bool):
        """Draw a single joystick preview on the given canvas."""
        canvas.delete("all")
        cx, cy, r = 50, 50, 40
        
        # Draw outer circle
        canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=self.FG_DIM, width=1)
        # Draw crosshair
        canvas.create_line(cx-r, cy, cx+r, cy, fill=self.FG_DIM, dash=(3, 4))
        canvas.create_line(cx, cy-r, cx, cy+r, fill=self.FG_DIM, dash=(3, 4))
        
        # Draw deadzone circle
        dz_r = int(r * self._dz_var.get())
        if dz_r > 0:
            canvas.create_oval(cx-dz_r, cy-dz_r, cx+dz_r, cy+dz_r,
                              outline="#555577", width=1, dash=(2, 3))
        
        # Draw position dot
        px = cx + nx * r
        py = cy - ny * r
        dot_r = 6
        
        # Color: green if enabled and active stick, dim otherwise
        if self._enabled_var.get() and active:
            color = self.GREEN
        else:
            color = self.FG_DIM
        
        canvas.create_oval(px-dot_r, py-dot_r, px+dot_r, py+dot_r,
                          fill=color, outline="")

    # ── Control callbacks ─────────────────────────────────────────────────────

    def _toggle_enabled(self):
        new_state = not self._enabled_var.get()
        self._enabled_var.set(new_state)
        with self.mapper._lock:
            self.mapper.enabled = new_state
        if new_state:
            self._toggle_btn.config(text="■", bg=self.ACCENT, fg="white")  # Stop icon
            self._set_status("Joystick active", ok=True)
        else:
            self._toggle_btn.config(text="▶", bg=self.BG2, fg=self.FG)  # Play icon
            self._set_status("Joystick disabled", ok=False)

    def _do_center(self):
        """Center physical mouse cursor + zero stick (without resetting triggers)."""
        # Center cursor and joystick, but preserve trigger values
        sw, sh = self.mapper._get_screen_size()
        cx, cy = sw // 2, sh // 2
        ctypes.windll.user32.SetCursorPos(cx, cy)
        
        if self.mapper._gamepad:
            try:
                if self.mapper.use_right_stick:
                    self.mapper._gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                else:
                    self.mapper._gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                self.mapper._gamepad.update()
            except Exception:
                pass
        
        self._set_status("Cursor centered", ok=True)

    def _open_website(self):
        """Open website in default browser."""
        import webbrowser
        webbrowser.open("https://www.youtube.com/@fakhryys")  # Change to actual website URL

    def _on_sens_change(self, val: float):
        with self.mapper._lock:
            self.mapper.sensitivity = val

    def _on_dz_change(self, val: float):
        with self.mapper._lock:
            self.mapper.deadzone = val

    def _on_stick_change(self):
        with self.mapper._lock:
            self.mapper.use_right_stick = (self._stick_var.get() == "Right")

    def _on_crosshair_change(self):
        """Toggle crosshair overlay."""
        if self._crosshair_var.get():
            self.crosshair.show()
        else:
            self.crosshair.hide()

    def _on_trigger_overlay_change(self):
        """Toggle trigger overlay."""
        if self._trigger_overlay_var.get():
            self.trigger_overlay.show()
        else:
            self.trigger_overlay.hide()

    def _on_separate_triggers_change(self):
        """Toggle separate trigger mode: save settings, apply hotkeys, rebuild Options tab."""
        self._apply_hotkeys()
        # Rebuild options tab so the correct hotkey rows are shown
        if self._active_tab == "options":
            self._switch_tab("options")

    def _on_reset_opposite_trigger_change(self):
        """Toggle reset opposite trigger mode: save settings and apply to hook."""
        self._apply_hotkeys()

    def _on_save_button_click(self):
        """Manual save button clicked - save settings and show confirmation."""
        self._save_settings()
        self._set_status("Settings saved successfully", ok=True)

    def _toggle_crosshair(self):
        """Toggle crosshair overlay (for hotkey)."""
        new_state = not self._crosshair_var.get()
        self._crosshair_var.set(new_state)
        self._on_crosshair_change()
    
    def _toggle_trigger_overlay(self):
        """Toggle trigger overlay (for hotkey)."""
        new_state = not self._trigger_overlay_var.get()
        self._trigger_overlay_var.set(new_state)
        self._on_trigger_overlay_change()

    def _switch_stick_threadsafe(self):
        """Called from hotkey thread — schedule on Tk main thread."""
        self.after(0, self._switch_stick)

    def _switch_stick(self):
        """Switch between left and right stick."""
        current = self._stick_var.get()
        new_stick = "Right" if current == "Left" else "Left"
        self._stick_var.set(new_stick)
        with self.mapper._lock:
            self.mapper.use_right_stick = (new_stick == "Right")
        self._set_status(f"Switched to {new_stick} stick", ok=True)

    # ── Settings helpers ──────────────────────────────────────────────────────

    def _apply_all_settings(self):
        """Push cfg values into mapper on startup."""
        with self.mapper._lock:
            self.mapper.sensitivity      = self.cfg["sensitivity"]
            self.mapper.deadzone         = self.cfg["deadzone"]
            self.mapper.use_right_stick  = (self.cfg["stick"] == "Right")
        
        # Apply crosshair setting
        if self.cfg.get("crosshair", False):
            # Delay showing crosshair to ensure window is ready
            self.after(100, self.crosshair.show)
        
        # Apply trigger overlay setting
        if self.cfg.get("trigger_overlay", False):
            # Delay showing trigger overlay to ensure window is ready
            self.after(100, self.trigger_overlay.show)
        
        # Apply hotkeys to the trigger hook
        self._apply_hotkeys()
    
    def _apply_hotkeys(self):
        """Apply hotkey settings to the trigger hook."""
        self.trigger_hook.set_hotkeys(
            self._hk_toggle_var.get(),
            self._hk_center_var.get(),
            self._hk_trigger_up_var.get(),
            self._hk_trigger_down_var.get(),
            self._hk_lt_up_var.get(),
            self._hk_lt_down_var.get(),
            self._hk_rt_up_var.get(),
            self._hk_rt_down_var.get(),
            self._hk_switch_stick_var.get(),
            self._hk_reset_triggers_var.get(),
            self._hk_crosshair_var.get(),
            self._hk_trigger_overlay_var.get(),
            separate_triggers=self._sep_triggers_var.get(),
            reset_opposite_trigger=self._reset_opposite_trigger_var.get()
        )

    def _save_settings(self):
        self.cfg["sensitivity"]           = self._sens_var.get()
        self.cfg["deadzone"]              = self._dz_var.get()
        self.cfg["stick"]                 = self._stick_var.get()
        self.cfg["crosshair"]             = self._crosshair_var.get()
        self.cfg["trigger_overlay"]       = self._trigger_overlay_var.get()
        self.cfg["separate_triggers"]     = self._sep_triggers_var.get()
        self.cfg["reset_opposite_trigger"] = self._reset_opposite_trigger_var.get()
        self.cfg["hotkey_toggle"]         = self._hk_toggle_var.get()
        self.cfg["hotkey_center"]         = self._hk_center_var.get()
        self.cfg["hotkey_trigger_up"]     = self._hk_trigger_up_var.get()
        self.cfg["hotkey_trigger_down"]   = self._hk_trigger_down_var.get()
        self.cfg["hotkey_lt_up"]          = self._hk_lt_up_var.get()
        self.cfg["hotkey_lt_down"]        = self._hk_lt_down_var.get()
        self.cfg["hotkey_rt_up"]          = self._hk_rt_up_var.get()
        self.cfg["hotkey_rt_down"]        = self._hk_rt_down_var.get()
        self.cfg["hotkey_switch_stick"]   = self._hk_switch_stick_var.get()
        self.cfg["hotkey_reset_triggers"] = self._hk_reset_triggers_var.get()
        self.cfg["hotkey_crosshair"]      = self._hk_crosshair_var.get()
        self.cfg["hotkey_trigger_overlay"] = self._hk_trigger_overlay_var.get()
        save_config(self.cfg)


    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, ok: bool):
        color = self.GREEN if ok else self.RED
        self._status_label.config(text=f"  {msg}", fg=color)

    def _set_icon(self):
        """Set window icon if icon.ico exists."""
        try:
            icon_path = os.path.join(RESOURCE_DIR, "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()

        # Get window size
        window_width  = self.winfo_width()

        # Get screen size
        screen_width  = self.winfo_screenwidth()

        # Place at top-right with a 12 px margin
        margin = 12
        x = screen_width - window_width - margin
        y = margin

        self.geometry(f"+{x}+{y}")

    # ── System tray ───────────────────────────────────────────────────────────

    def _make_tray_icon_image(self):
        """Load icon.ico if available, otherwise create a default icon."""
        try:
            icon_path = os.path.join(RESOURCE_DIR, "icon.ico")
            if os.path.exists(icon_path):
                # Load the .ico file
                return Image.open(icon_path)
        except Exception:
            pass
        
        # Fallback to programmatic icon
        size = 64
        img  = Image.new("RGB", (size, size), color=(30, 31, 46))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], outline=(88, 101, 242), width=4)
        draw.ellipse([26, 26, 38, 38], fill=(67, 181, 129))
        return img

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._tray_show, default=True),
            pystray.MenuItem("Exit", self._tray_quit),
        )
        self._tray_icon = pystray.Icon(
            "vCTRL", self._make_tray_icon_image(), "vCTRL — Virtual Controller", menu)
        t = threading.Thread(target=self._tray_icon.run, daemon=True)
        t.start()

    def _tray_show(self, icon=None, item=None):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _tray_quit(self, icon=None, item=None):   self.after(0, self._actual_close)

    # ── Window close ──────────────────────────────────────────────────────────

    def _on_close(self):
        """Called when window close (X) button is clicked - minimize to tray instead"""
        if self._tray_icon:
            self.withdraw()  # Hide window instead of destroying
        else:
            self._actual_close()

    def _actual_close(self):
        """Actually close the application"""
        self.crosshair.hide()
        self.trigger_overlay.hide()
        self.mapper.stop()
        self.trigger_hook.stop()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    cfg          = load_config()
    mapper       = MouseJoystickMapper()
    trigger_hook = TriggerHook(mapper)
    app          = App(mapper, None, trigger_hook, cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
