# -*- coding: utf-8 -*-
"""
Configuration file management.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .models import AppConfig
from ..system.paths import get_config_path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages loading and saving application configuration."""
    
    def __init__(self):
        self.config_path = get_config_path()
    
    def load(self) -> AppConfig:
        """Load configuration from file, returning defaults if not found."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                config = AppConfig.from_dict(data)
                config.validate()
                return config
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}")
        
        return AppConfig()
    
    def save(self, config: AppConfig) -> bool:
        """Save configuration to file."""
        try:
            config.validate()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
            return False
