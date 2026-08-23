# -*- coding: utf-8 -*-
"""
Hotkey parsing and formatting utilities.
"""

from typing import Optional, Tuple
from ..constants import MODIFIER_MAP, VK_CODE_MAP


def parse_hotkey(combo: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse a hotkey combination string into modifier flags and virtual key code.
    
    Args:
        combo: Hotkey string like 'ctrl+shift+t' or 'capslock'
    
    Returns:
        Tuple of (modifier_flags, vk_code) or (None, None) if parsing fails
    
    Examples:
        >>> parse_hotkey('ctrl+shift+t')
        (6, 84)  # MOD_CONTROL | MOD_SHIFT, VK_T
        >>> parse_hotkey('capslock')
        (0, 20)  # no modifiers, VK_CAPITAL
    """
    if not combo:
        return None, None
    
    parts = [p.strip().lower() for p in combo.split("+")]
    mods = 0
    vk = None
    
    for part in parts:
        if part in MODIFIER_MAP:
            mods |= MODIFIER_MAP[part]
        elif part in VK_CODE_MAP:
            vk = VK_CODE_MAP[part]
        else:
            try:
                vk = int(part)
            except ValueError:
                return None, None
    
    if vk is None:
        return None, None
    
    return mods, vk


def format_hotkey(mods: int, vk: int) -> str:
    """
    Format modifier flags and virtual key code back into a readable string.
    
    Args:
        mods: Modifier flags
        vk: Virtual key code
    
    Returns:
        Formatted hotkey string like 'ctrl+shift+t'
    """
    parts = []
    
    reverse_mod_map = {v: k for k, v in MODIFIER_MAP.items() if k in ('ctrl', 'alt', 'shift', 'win')}
    for mod_flag, mod_name in sorted(reverse_mod_map.items()):
        if mods & mod_flag:
            parts.append(mod_name)
    
    reverse_vk_map = {v: k for k, v in VK_CODE_MAP.items()}
    if vk in reverse_vk_map:
        parts.append(reverse_vk_map[vk])
    else:
        parts.append(str(vk))
    
    return "+".join(parts)
