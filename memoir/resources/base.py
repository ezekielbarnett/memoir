"""
Base class for resources.

Resources are versioned, editable data that services consume.
They're loaded from YAML files and can be modified at runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml


class Resource(ABC):
    """
    Base class for all resources.
    
    Resources are data objects that can be:
    - Loaded from YAML files
    - Versioned
    - Referenced by ID from product definitions
    
    Examples:
        - Question banks
        - Prompt templates
        - Document templates
    """
    
    @property
    @abstractmethod
    def resource_id(self) -> str:
        """Unique identifier for this resource."""
        pass
    
    @property
    def resource_type(self) -> str:
        """Type of resource (questions, prompts, templates, etc.)."""
        return self.__class__.__name__.lower()
    
    @property
    def version(self) -> int:
        """Version number of this resource."""
        return 1
    
    @property
    def name(self) -> str:
        """Human-readable name."""
        return self.resource_id.replace("_", " ").title()
    
    @property
    def description(self) -> str:
        """Description of this resource."""
        return ""
    
    @property
    def tags(self) -> list[str]:
        """Tags for categorization."""
        return []
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Resource:
        """Create a resource from a dictionary."""
        pass
    
    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        pass
    
    @classmethod
    def from_yaml(cls, path: Path | str) -> Resource:
        """Load a resource from a YAML file."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def to_yaml(self, path: Path | str) -> None:
        """Save to a YAML file."""
        path = Path(path)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.resource_id}, v{self.version})>"

