"""
Base collector class for Gitstats3.

Provides common functionality shared by all data collectors.
"""

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, Any, Optional

from .gitstats_config import get_config


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Provides common initialization, caching, and data access patterns.
    """
    
    def __init__(self):
        """Initialize the base collector."""
        self.stamp_created = time.time()
        self.cache: Dict[str, Any] = {}
        self._data: Dict[str, Any] = {}
        self._config = get_config()
    
    @abstractmethod
    def collect(self) -> None:
        """
        Collect data from the repository.
        
        Subclasses must implement this method to gather their specific data.
        """
        pass
    
    @abstractmethod
    def refine(self) -> None:
        """
        Refine collected data after initial collection.
        
        Called after collect() to compute derived metrics.
        """
        pass
    
    def get_data(self) -> Dict[str, Any]:
        """
        Get all collected data.
        
        Returns:
            Dictionary containing all collected data
        """
        return self._data
    
    def get_stamp_created(self) -> float:
        """
        Get the timestamp when this collector was created.
        
        Returns:
            Unix timestamp
        """
        return self.stamp_created
    
    def clear_cache(self) -> None:
        """Clear the internal cache to free memory."""
        self.cache.clear()
    
    def _create_nested_defaultdict(self, depth: int = 2):
        """
        Create a nested defaultdict of specified depth.
        
        Args:
            depth: Number of nesting levels
            
        Returns:
            Nested defaultdict
        """
        if depth <= 1:
            return defaultdict(int)
        return defaultdict(lambda: self._create_nested_defaultdict(depth - 1))
    
    def _optimize_memory(self) -> None:
        """
        Optimize memory usage by converting defaultdicts to regular dicts.
        
        Call this after data collection is complete.
        """
        def convert_defaultdict(obj):
            if isinstance(obj, defaultdict):
                obj = dict(obj)
                for key, value in obj.items():
                    obj[key] = convert_defaultdict(value)
            return obj
        
        self._data = convert_defaultdict(self._data)
        self.cache.clear()
