# -*- coding: utf-8 -*-
"""
Pure mathematical functions for joystick value calculations.
"""

import math
from typing import Tuple


def normalize_cursor_position(cursor_x: int, cursor_y: int, 
                              screen_width: int, screen_height: int) -> Tuple[float, float]:
    """
    Normalize cursor position from screen coordinates to [-1, 1] range.
    
    Args:
        cursor_x: Cursor X position in pixels
        cursor_y: Cursor Y position in pixels
        screen_width: Screen width in pixels
        screen_height: Screen height in pixels
    
    Returns:
        Tuple of (normalized_x, normalized_y) in range [-1, 1]
    """
    nx = (cursor_x / screen_width) * 2.0 - 1.0
    ny = -((cursor_y / screen_height) * 2.0 - 1.0)
    return nx, ny


def apply_sensitivity(x: float, y: float, sensitivity: float) -> Tuple[float, float]:
    """
    Apply sensitivity multiplier and clamp to [-1, 1] range.
    
    Args:
        x: Normalized X value
        y: Normalized Y value
        sensitivity: Sensitivity multiplier (typically 0.1 to 3.0)
    
    Returns:
        Tuple of (adjusted_x, adjusted_y) clamped to [-1, 1]
    """
    x = max(-1.0, min(1.0, x * sensitivity))
    y = max(-1.0, min(1.0, y * sensitivity))
    return x, y


def apply_deadzone(x: float, y: float, deadzone: float) -> Tuple[float, float]:
    """
    Apply circular deadzone with rescaling.
    
    Values inside the deadzone are zeroed. Values outside are rescaled
    to maintain smooth transition from deadzone edge to maximum range.
    
    Args:
        x: Input X value in range [-1, 1]
        y: Input Y value in range [-1, 1]
        deadzone: Deadzone radius (typically 0.0 to 0.5)
    
    Returns:
        Tuple of (output_x, output_y) with deadzone applied
    """
    magnitude = math.sqrt(x * x + y * y)
    
    if magnitude < deadzone or magnitude == 0.0:
        return 0.0, 0.0
    
    # Avoid division by zero when deadzone is 1.0 (shouldn't happen in normal use)
    if deadzone >= 1.0:
        return 0.0, 0.0
    
    scale = (magnitude - deadzone) / (1.0 - deadzone)
    scale = min(scale, 1.0)
    
    return (x / magnitude) * scale, (y / magnitude) * scale


def invert_y_axis(y: float) -> float:
    """
    Invert Y axis value.
    
    Args:
        y: Y value in range [-1, 1]
    
    Returns:
        Inverted Y value
    """
    return -y
