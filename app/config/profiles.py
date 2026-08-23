# -*- coding: utf-8 -*-
"""
Profile management for saving and loading configuration presets.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from .models import AppConfig
from ..system.paths import get_profiles_dir, ensure_profiles_dir

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages profile storage and retrieval."""
    
    def __init__(self):
        self.profiles_dir = get_profiles_dir()
        ensure_profiles_dir()
    
    def list_profiles(self) -> List[str]:
        """Get list of available profile names."""
        try:
            if not self.profiles_dir.exists():
                return []
            
            profiles = []
            for file_path in self.profiles_dir.glob("*.json"):
                profiles.append(file_path.stem)
            
            return sorted(profiles)
        except Exception as e:
            logger.error(f"Failed to list profiles: {e}")
            return []
    
    def load(self, name: str) -> Optional[AppConfig]:
        """Load a profile by name."""
        try:
            profile_path = self.profiles_dir / f"{name}.json"
            if not profile_path.exists():
                logger.warning(f"Profile '{name}' not found")
                return None
            
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = AppConfig.from_dict(data)
            config.validate()
            return config
        except Exception as e:
            logger.error(f"Failed to load profile '{name}': {e}")
            return None
    
    def save(self, name: str, config: AppConfig) -> bool:
        """Save configuration as a profile."""
        try:
            ensure_profiles_dir()
            profile_path = self.profiles_dir / f"{name}.json"
            
            config.validate()
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            logger.info(f"Saved profile '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to save profile '{name}': {e}")
            return False
    
    def delete(self, name: str) -> bool:
        """Delete a profile by name."""
        try:
            profile_path = self.profiles_dir / f"{name}.json"
            if profile_path.exists():
                profile_path.unlink()
                logger.info(f"Deleted profile '{name}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete profile '{name}': {e}")
            return False
