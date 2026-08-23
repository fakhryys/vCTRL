# -*- coding: utf-8 -*-
"""
System tray icon management.
"""

import threading
import logging
from pathlib import Path
from typing import Optional, Callable

from .paths import get_resource_dir

logger = logging.getLogger(__name__)

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    pystray = None
    Image = None
    ImageDraw = None


class TrayIcon:
    """System tray icon with show/quit menu."""
    
    def __init__(self, on_show: Callable, on_quit: Callable):
        if not TRAY_AVAILABLE:
            raise RuntimeError("pystray and Pillow are not installed")
        
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon = None
        self._thread = None
    
    def start(self):
        """Start the tray icon."""
        if self._icon:
            return
        
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._handle_show, default=True),
            pystray.MenuItem("Exit", self._handle_quit),
        )
        
        image = self._create_icon_image()
        self._icon = pystray.Icon(
            "vCTRL",
            image,
            "vCTRL — Virtual Controller",
            menu
        )
        
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="TrayIcon")
        self._thread.start()
    
    def stop(self):
        """Stop the tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.error(f"Error stopping tray icon: {e}")
            self._icon = None
    
    def _handle_show(self, icon=None, item=None):
        """Handle show menu item."""
        if self._on_show:
            self._on_show()
    
    def _handle_quit(self, icon=None, item=None):
        """Handle quit menu item."""
        if self._on_quit:
            self._on_quit()
    
    def _create_icon_image(self) -> Image:
        """Create tray icon image, loading from file or generating default."""
        icon_path = get_resource_dir() / "icon.ico"
        
        try:
            if icon_path.exists():
                return Image.open(icon_path)
        except Exception as e:
            logger.warning(f"Failed to load icon from {icon_path}: {e}")
        
        size = 64
        img = Image.new("RGB", (size, size), color=(30, 31, 46))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], outline=(88, 101, 242), width=4)
        draw.ellipse([26, 26, 38, 38], fill=(67, 181, 129))
        return img
