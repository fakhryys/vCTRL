# -*- coding: utf-8 -*-
"""
Path resolution utilities with PyInstaller support.
"""

import os
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """
    Get the application directory where config and profiles should be stored.
    
    For PyInstaller executables, this is the directory containing the .exe.
    For Python scripts, this is the directory containing the script.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


def get_resource_dir() -> Path:
    """
    Get the directory containing bundled resources (icons, etc.).
    
    For PyInstaller executables, this is the temporary extraction directory.
    For Python scripts, this is the script directory.
    """
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', get_app_dir()))
    else:
        return get_app_dir()


def get_config_path() -> Path:
    """Get the path to the main configuration file."""
    return get_app_dir() / "config.json"


def get_profiles_dir() -> Path:
    """Get the directory where profiles are stored."""
    return get_app_dir() / "profiles"


def ensure_profiles_dir():
    """Create profiles directory if it doesn't exist."""
    profiles_dir = get_profiles_dir()
    try:
        profiles_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
