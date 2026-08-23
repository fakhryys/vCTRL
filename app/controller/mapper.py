# -*- coding: utf-8 -*-
"""
Mouse to joystick mapper with virtual controller management.
"""

import threading
import time
import ctypes
import logging

from .math_utils import normalize_cursor_position, apply_sensitivity, apply_deadzone, invert_y_axis
from ..constants import POLL_HZ

logger = logging.getLogger(__name__)

try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    VGAMEPAD_AVAILABLE = False


class MouseJoystickMapper:
    """
    Polls mouse cursor position and maps it to virtual gamepad stick axes.
    Runs in a background thread at ~120Hz.
    """
    
    def __init__(self):
        self._enabled = False
        self._sensitivity = 1.0
        self._deadzone = 0.05
        self._use_right_stick = False
        self._invert_y = False
        
        self._left_trigger = 0.0
        self._right_trigger = 0.0
        
        self._gamepad = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        self._screen_width = 1920
        self._screen_height = 1080
    
    def start(self):
        """Start the mapper and virtual controller."""
        if not VGAMEPAD_AVAILABLE:
            raise RuntimeError("vgamepad is not installed.\nRun: pip install vgamepad")
        
        if self._thread and self._thread.is_alive():
            return
        
        self._gamepad = vg.VX360Gamepad()
        
        self._gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self._gamepad.update()
        time.sleep(0.05)
        self._gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        self._gamepad.update()
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="MouseJoystickMapper")
        self._thread.start()
    
    def stop(self):
        """Stop the mapper and reset the virtual controller."""
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
    
    def set_enabled(self, enabled: bool):
        """Enable or disable joystick mapping."""
        with self._lock:
            self._enabled = enabled
    
    def is_enabled(self) -> bool:
        """Check if joystick mapping is enabled."""
        with self._lock:
            return self._enabled
    
    def set_sensitivity(self, sensitivity: float):
        """Set sensitivity multiplier."""
        with self._lock:
            self._sensitivity = sensitivity
    
    def set_deadzone(self, deadzone: float):
        """Set deadzone radius."""
        with self._lock:
            self._deadzone = deadzone
    
    def set_stick(self, use_right: bool):
        """Set which stick to control (True = right, False = left)."""
        with self._lock:
            self._use_right_stick = use_right
    
    def set_invert_y(self, invert: bool):
        """Set Y-axis inversion."""
        with self._lock:
            self._invert_y = invert
    
    def set_trigger_values(self, left: float, right: float):
        """Set trigger values (0.0 to 1.0)."""
        with self._lock:
            self._left_trigger = max(0.0, min(1.0, left))
            self._right_trigger = max(0.0, min(1.0, right))
    
    def adjust_trigger(self, left_delta: float, right_delta: float):
        """Adjust trigger values by delta amounts."""
        with self._lock:
            self._left_trigger = max(0.0, min(1.0, self._left_trigger + left_delta))
            self._right_trigger = max(0.0, min(1.0, self._right_trigger + right_delta))
    
    def get_trigger_values(self) -> tuple:
        """Get current trigger values."""
        with self._lock:
            return self._left_trigger, self._right_trigger
    
    def reset_triggers(self):
        """Reset both triggers to zero."""
        with self._lock:
            self._left_trigger = 0.0
            self._right_trigger = 0.0
    
    def center_cursor(self):
        """Move cursor to screen center and zero the stick."""
        screen_width, screen_height = self._get_screen_size()
        center_x, center_y = screen_width // 2, screen_height // 2
        ctypes.windll.user32.SetCursorPos(center_x, center_y)
        
        if self._gamepad:
            try:
                with self._lock:
                    use_right = self._use_right_stick
                
                if use_right:
                    self._gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                else:
                    self._gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                self._gamepad.update()
            except Exception as e:
                logger.error(f"Failed to center joystick: {e}")
    
    def _get_screen_size(self):
        """Get current screen dimensions."""
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    
    def _get_cursor_pos(self):
        """Get current cursor position."""
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    
    def _poll_loop(self):
        """Background polling loop running at ~120Hz."""
        interval = 1.0 / POLL_HZ
        self._screen_width, self._screen_height = self._get_screen_size()
        
        while not self._stop_event.is_set():
            t0 = time.perf_counter()
            
            with self._lock:
                enabled = self._enabled
                sensitivity = self._sensitivity
                deadzone = self._deadzone
                use_right = self._use_right_stick
                invert_y = self._invert_y
                lt = self._left_trigger
                rt = self._right_trigger
            
            if self._gamepad:
                try:
                    self._gamepad.left_trigger_float(value_float=lt)
                    self._gamepad.right_trigger_float(value_float=rt)
                    
                    if enabled:
                        cursor_x, cursor_y = self._get_cursor_pos()
                        
                        nx, ny = normalize_cursor_position(
                            cursor_x, cursor_y,
                            self._screen_width, self._screen_height
                        )
                        
                        nx, ny = apply_sensitivity(nx, ny, sensitivity)
                        
                        if invert_y:
                            ny = invert_y_axis(ny)
                        
                        nx, ny = apply_deadzone(nx, ny, deadzone)
                        
                        if use_right:
                            self._gamepad.right_joystick_float(x_value_float=nx, y_value_float=ny)
                        else:
                            self._gamepad.left_joystick_float(x_value_float=nx, y_value_float=ny)
                    
                    self._gamepad.update()
                except Exception as e:
                    logger.error(f"Error in poll loop: {e}")
            
            elapsed = time.perf_counter() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
