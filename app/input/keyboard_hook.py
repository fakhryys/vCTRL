# -*- coding: utf-8 -*-
"""
Low-level keyboard hook for hotkey detection.
"""

import ctypes
import threading
import time
import logging
from typing import Optional, Callable
from ctypes import wintypes

from .models import HotkeyConfig
from .parser import parse_hotkey
from ..constants import (
    WH_KEYBOARD_LL, WM_KEYDOWN, WM_SYSKEYDOWN, WM_QUIT,
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN,
    VK_MENU, VK_CONTROL, VK_SHIFT, VK_LWIN
)

logger = logging.getLogger(__name__)

_hook_callback_ref = None


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    """Win32 keyboard hook structure."""
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class KeyboardHook:
    """
    Low-level keyboard hook for detecting hotkey combinations.
    
    Runs in a separate thread and invokes registered callbacks when
    hotkeys are pressed.
    """
    
    def __init__(self, mapper):
        self._mapper = mapper
        self._hook = None
        self._thread = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        
        self._config = HotkeyConfig()
        
        self._parsed_hotkeys = {}
        self._parse_all_hotkeys()
        
        self._on_toggle = None
        self._on_center = None
        self._on_switch_stick = None
        self._on_reset_triggers = None
        self._on_toggle_crosshair = None
        self._on_toggle_trigger_overlay = None
        self._on_trigger_change = None
    
    def set_callbacks(self, on_toggle: Optional[Callable] = None,
                     on_center: Optional[Callable] = None,
                     on_switch_stick: Optional[Callable] = None,
                     on_reset_triggers: Optional[Callable] = None,
                     on_toggle_crosshair: Optional[Callable] = None,
                     on_toggle_trigger_overlay: Optional[Callable] = None,
                     on_trigger_change: Optional[Callable[[float, float], None]] = None):
        """Set callback functions for hotkey events."""
        self._on_toggle = on_toggle
        self._on_center = on_center
        self._on_switch_stick = on_switch_stick
        self._on_reset_triggers = on_reset_triggers
        self._on_toggle_crosshair = on_toggle_crosshair
        self._on_toggle_trigger_overlay = on_toggle_trigger_overlay
        self._on_trigger_change = on_trigger_change
    
    def update_config(self, config: HotkeyConfig):
        """Update hotkey configuration."""
        self._config = config
        self._parse_all_hotkeys()
    
    def _parse_all_hotkeys(self):
        """Parse all hotkey strings into (mods, vk) tuples."""
        self._parsed_hotkeys = {
            'toggle': parse_hotkey(self._config.toggle),
            'center': parse_hotkey(self._config.center),
            'trigger_up': parse_hotkey(self._config.trigger_up),
            'trigger_down': parse_hotkey(self._config.trigger_down),
            'lt_up': parse_hotkey(self._config.lt_up),
            'lt_down': parse_hotkey(self._config.lt_down),
            'rt_up': parse_hotkey(self._config.rt_up),
            'rt_down': parse_hotkey(self._config.rt_down),
            'switch_stick': parse_hotkey(self._config.switch_stick),
            'reset_triggers': parse_hotkey(self._config.reset_triggers),
            'crosshair': parse_hotkey(self._config.crosshair),
            'trigger_overlay': parse_hotkey(self._config.trigger_overlay),
        }
    
    def start(self):
        """Start the keyboard hook thread."""
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="KeyboardHook")
        self._thread.start()
        self._ready_event.wait(timeout=2.0)
    
    def stop(self):
        """Stop the keyboard hook thread."""
        self._stop_event.set()
        try:
            if self._thread:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread.ident,
                    WM_QUIT,
                    0, 0
                )
        except Exception as e:
            logger.error(f"Error stopping keyboard hook: {e}")
    
    def _check_modifiers(self, required_mods: int) -> bool:
        """Check if required modifier keys are currently pressed."""
        if required_mods == 0:
            return True
        
        result = True
        if required_mods & MOD_ALT:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(VK_MENU) & 0x8000 != 0)
        if required_mods & MOD_CONTROL:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000 != 0)
        if required_mods & MOD_SHIFT:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(VK_SHIFT) & 0x8000 != 0)
        if required_mods & MOD_WIN:
            result = result and (ctypes.windll.user32.GetAsyncKeyState(VK_LWIN) & 0x8000 != 0)
        
        return result
    
    def _handle_keypress(self, vk: int):
        """Handle a key press event."""
        if self._config.separate_triggers:
            self._handle_separate_triggers(vk)
        else:
            self._handle_combined_triggers(vk)
        
        self._handle_common_hotkeys(vk)
    
    def _handle_separate_triggers(self, vk: int):
        """Handle trigger hotkeys in separate mode."""
        mods, vk_code = self._parsed_hotkeys.get('lt_up', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_lt(+self._config.trigger_intensity)
            return
        
        mods, vk_code = self._parsed_hotkeys.get('lt_down', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_lt(-self._config.trigger_intensity)
            return
        
        mods, vk_code = self._parsed_hotkeys.get('rt_up', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_rt(+self._config.trigger_intensity)
            return
        
        mods, vk_code = self._parsed_hotkeys.get('rt_down', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_rt(-self._config.trigger_intensity)
            return
    
    def _handle_combined_triggers(self, vk: int):
        """Handle trigger hotkeys in combined mode."""
        mods, vk_code = self._parsed_hotkeys.get('trigger_up', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_triggers(+self._config.trigger_intensity)
            return
        
        mods, vk_code = self._parsed_hotkeys.get('trigger_down', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            self._adjust_triggers(-self._config.trigger_intensity)
            return
    
    def _handle_common_hotkeys(self, vk: int):
        """Handle hotkeys common to both modes."""
        mods, vk_code = self._parsed_hotkeys.get('toggle', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_toggle:
                try:
                    self._on_toggle()
                except Exception as e:
                    logger.error(f"Error in toggle callback: {e}")
            return
        
        mods, vk_code = self._parsed_hotkeys.get('center', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_center:
                try:
                    self._on_center()
                except Exception as e:
                    logger.error(f"Error in center callback: {e}")
            return
        
        mods, vk_code = self._parsed_hotkeys.get('switch_stick', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_switch_stick:
                try:
                    self._on_switch_stick()
                except Exception as e:
                    logger.error(f"Error in switch_stick callback: {e}")
            return
        
        mods, vk_code = self._parsed_hotkeys.get('reset_triggers', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_reset_triggers:
                try:
                    self._on_reset_triggers()
                except Exception as e:
                    logger.error(f"Error in reset_triggers callback: {e}")
            return
        
        mods, vk_code = self._parsed_hotkeys.get('crosshair', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_toggle_crosshair:
                try:
                    self._on_toggle_crosshair()
                except Exception as e:
                    logger.error(f"Error in crosshair callback: {e}")
            return
        
        mods, vk_code = self._parsed_hotkeys.get('trigger_overlay', (None, None))
        if vk == vk_code and self._check_modifiers(mods):
            if self._on_toggle_trigger_overlay:
                try:
                    self._on_toggle_trigger_overlay()
                except Exception as e:
                    logger.error(f"Error in trigger_overlay callback: {e}")
            return
    
    def _adjust_triggers(self, step: float):
        """Adjust both triggers by the same amount."""
        lt, rt = self._mapper.get_trigger_values()
        lt = max(0.0, min(1.0, lt + step))
        rt = max(0.0, min(1.0, rt + step))
        self._mapper.set_trigger_values(lt, rt)
        
        if self._on_trigger_change:
            try:
                self._on_trigger_change(lt, rt)
            except Exception as e:
                logger.error(f"Error in trigger_change callback: {e}")
    
    def _adjust_lt(self, step: float):
        """Adjust left trigger only."""
        lt, rt = self._mapper.get_trigger_values()
        lt = max(0.0, min(1.0, lt + step))
        
        if self._config.reset_opposite_trigger and step > 0 and lt > 0:
            rt = 0.0
        
        self._mapper.set_trigger_values(lt, rt)
        
        if self._on_trigger_change:
            try:
                self._on_trigger_change(lt, rt)
            except Exception as e:
                logger.error(f"Error in trigger_change callback: {e}")
    
    def _adjust_rt(self, step: float):
        """Adjust right trigger only."""
        lt, rt = self._mapper.get_trigger_values()
        rt = max(0.0, min(1.0, rt + step))
        
        if self._config.reset_opposite_trigger and step > 0 and rt > 0:
            lt = 0.0
        
        self._mapper.set_trigger_values(lt, rt)
        
        if self._on_trigger_change:
            try:
                self._on_trigger_change(lt, rt)
            except Exception as e:
                logger.error(f"Error in trigger_change callback: {e}")
    
    def _run(self):
        """Main hook thread loop."""
        global _hook_callback_ref
        
        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(_KBDLLHOOKSTRUCT)
        )
        
        def low_level_keyboard_proc(nCode, wParam, lParam):
            if nCode >= 0 and (wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN):
                event = lParam.contents
                self._handle_keypress(event.vkCode)
            
            return ctypes.windll.user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
        
        _hook_callback_ref = HOOKPROC(low_level_keyboard_proc)
        self._hook = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            _hook_callback_ref,
            None,
            0
        )
        
        self._ready_event.set()
        
        msg = wintypes.MSG()
        while not self._stop_event.is_set():
            ret = ctypes.windll.user32.PeekMessageW(
                ctypes.byref(msg), None, 0, 0, 1
            )
            if ret:
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        
        if self._hook:
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
