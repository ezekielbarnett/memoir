"""
Product definition loader.

Loads product definitions from YAML files and registers them
with the system. Product definitions are the declarative configuration
that wires together resources, services, and interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from memoir.core.registry import Registry, get_registry
from memoir.products.config import (
    CollectionConfig,
    OutputConfig,
    PhaseConfig,
    NotificationsConfig,
    UIConfig,
    SubjectConfig,
    ResourceRefs,
    ProjectionDefinition,
)


@dataclass
class ProductDefinition:
    """
    Complete product definition.
    
    This is the parsed representation of a product YAML file.
    It contains all configuration needed to run a product.
    
    Key concept: Content is primary, documents are projections.
    The 'output' config defines how content becomes viewable documents.
    """
    
    product_id: str
    name: str
    description: str = ""
    version: int = 1
    
    # Subject configuration
    subject: SubjectConfig = field(default_factory=SubjectConfig)
    
    # Resource references
    resources: ResourceRefs = field(default_factory=ResourceRefs)
    
    # Phased collection journey (optional - if empty, no phases)
    phases: list[PhaseConfig] = field(default_factory=list)
    
    # Collection configuration (used when no phases, or as defaults for phases)
    collection: CollectionConfig = field(default_factory=CollectionConfig)
    
    # Output configuration (content -> document projections)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # Notifications
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    
    # UI configuration
    ui: UIConfig = field(default_factory=UIConfig)
    
    # Raw config for extensions
    raw_config: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_phased(self) -> bool:
        """Whether this product uses phased collection."""
        return len(self.phases) > 0
    
    def get_phase(self, phase_id: str) -> PhaseConfig | None:
        """Get a phase by ID."""
        for phase in self.phases:
            if phase.phase_id == phase_id:
                return phase
        return None
    
    def get_phases_in_order(self) -> list[PhaseConfig]:
        """Get phases sorted by order."""
        return sorted(self.phases, key=lambda p: p.order)
    
    def get_first_phase(self) -> PhaseConfig | None:
        """Get the first phase (lowest order)."""
        phases = self.get_phases_in_order()
        return phases[0] if phases else None
    
    def get_next_phase(self, current_phase_id: str) -> PhaseConfig | None:
        """Get the next phase after the given one."""
        phases = self.get_phases_in_order()
        for i, phase in enumerate(phases):
            if phase.phase_id == current_phase_id and i + 1 < len(phases):
                return phases[i + 1]
        return None
    
    def get_default_projection(self) -> ProjectionDefinition | None:
        """Get the default projection for this product."""
        return self.output.get_default_projection()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductDefinition:
        # Parse phases
        phases = [
            PhaseConfig.from_dict(p)
            for p in data.get("phases", [])
        ]
        
        return cls(
            product_id=data["product"],
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", 1),
            subject=SubjectConfig.from_dict(data.get("subject", {})),
            resources=ResourceRefs.from_dict(data.get("resources", {})),
            phases=phases,
            collection=CollectionConfig.from_dict(data.get("collection", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            notifications=NotificationsConfig.from_dict(data.get("notifications", {})),
            ui=UIConfig.from_dict(data.get("ui", {})),
            raw_config=data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert back to dictionary (for serialization)."""
        return self.raw_config


class ProductLoader:
    """
    Loads product definitions from YAML files.
    
    Products can be loaded from individual files or from a directory
    containing multiple product definitions.
    """
    
    def __init__(self, registry: Registry | None = None):
        self.registry = registry or get_registry()
    
    def load_file(self, path: Path | str) -> ProductDefinition:
        """Load a single product definition from a YAML file."""
        path = Path(path)
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        product = ProductDefinition.from_dict(data)
        
        # Register with the registry
        self.registry.register_product(product.product_id, product.to_dict())
        
        return product
    
    def load_directory(self, directory: Path | str) -> list[ProductDefinition]:
        """Load all product definitions from a directory."""
        directory = Path(directory)
        products = []
        
        for path in directory.glob("*.yaml"):
            try:
                product = self.load_file(path)
                products.append(product)
            except Exception as e:
                print(f"Warning: Failed to load {path}: {e}")
        
        for path in directory.glob("*.yml"):
            try:
                product = self.load_file(path)
                products.append(product)
            except Exception as e:
                print(f"Warning: Failed to load {path}: {e}")
        
        return products
    
    def load_from_dict(self, data: dict[str, Any]) -> ProductDefinition:
        """Load a product definition from a dictionary."""
        product = ProductDefinition.from_dict(data)
        self.registry.register_product(product.product_id, product.to_dict())
        return product
    
    def get_product(self, product_id: str) -> ProductDefinition:
        """Get a loaded product definition by ID."""
        config = self.registry.get_product(product_id)
        return ProductDefinition.from_dict(config)
