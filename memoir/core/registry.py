"""
Registry for services, interfaces, and resources.

The registry is the central place where all pluggable components
are registered and looked up. It enables the declarative product
definitions to reference components by name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from memoir.services.base import Service
    from memoir.interfaces.base import InputInterface, OutputInterface
    from memoir.resources.base import Resource

T = TypeVar("T")


class RegistryError(Exception):
    """Raised when there's an error with the registry."""
    pass


class Registry:
    """
    Central registry for all pluggable components.
    
    Components register themselves by ID, and product definitions
    reference them by ID. This decouples the wiring from the implementation.
    """
    
    def __init__(self):
        # Service registry: service_id -> service instance
        self._services: dict[str, Service] = {}
        
        # Interface registries: interface_id -> interface instance
        self._input_interfaces: dict[str, InputInterface] = {}
        self._output_interfaces: dict[str, OutputInterface] = {}
        
        # Resource registries: resource_type -> resource_id -> resource
        self._resources: dict[str, dict[str, Resource]] = {
            "questions": {},
            "prompts": {},
            "templates": {},
        }
        
        # Product definitions: product_id -> product config
        self._products: dict[str, dict[str, Any]] = {}
    
    # =========================================================================
    # Services
    # =========================================================================
    
    def register_service(self, service: Service) -> None:
        """Register a service by its ID."""
        if service.service_id in self._services:
            raise RegistryError(f"Service '{service.service_id}' is already registered")
        self._services[service.service_id] = service
    
    def get_service(self, service_id: str) -> Service:
        """Get a service by ID."""
        if service_id not in self._services:
            raise RegistryError(f"Service '{service_id}' not found")
        return self._services[service_id]
    
    def list_services(self) -> list[str]:
        """List all registered service IDs."""
        return list(self._services.keys())
    
    # =========================================================================
    # Input Interfaces
    # =========================================================================
    
    def register_input_interface(self, interface: InputInterface) -> None:
        """Register an input interface by its ID."""
        if interface.interface_id in self._input_interfaces:
            raise RegistryError(
                f"Input interface '{interface.interface_id}' is already registered"
            )
        self._input_interfaces[interface.interface_id] = interface
    
    def get_input_interface(self, interface_id: str) -> InputInterface:
        """Get an input interface by ID."""
        if interface_id not in self._input_interfaces:
            raise RegistryError(f"Input interface '{interface_id}' not found")
        return self._input_interfaces[interface_id]
    
    def list_input_interfaces(self) -> list[str]:
        """List all registered input interface IDs."""
        return list(self._input_interfaces.keys())
    
    # =========================================================================
    # Output Interfaces
    # =========================================================================
    
    def register_output_interface(self, interface: OutputInterface) -> None:
        """Register an output interface by its ID."""
        if interface.interface_id in self._output_interfaces:
            raise RegistryError(
                f"Output interface '{interface.interface_id}' is already registered"
            )
        self._output_interfaces[interface.interface_id] = interface
    
    def get_output_interface(self, interface_id: str) -> OutputInterface:
        """Get an output interface by ID."""
        if interface_id not in self._output_interfaces:
            raise RegistryError(f"Output interface '{interface_id}' not found")
        return self._output_interfaces[interface_id]
    
    def list_output_interfaces(self) -> list[str]:
        """List all registered output interface IDs."""
        return list(self._output_interfaces.keys())
    
    # =========================================================================
    # Resources
    # =========================================================================
    
    def register_resource(self, resource_type: str, resource: Resource) -> None:
        """Register a resource by type and ID."""
        if resource_type not in self._resources:
            self._resources[resource_type] = {}
        
        if resource.resource_id in self._resources[resource_type]:
            raise RegistryError(
                f"Resource '{resource.resource_id}' of type '{resource_type}' "
                "is already registered"
            )
        self._resources[resource_type][resource.resource_id] = resource
    
    def get_resource(self, resource_type: str, resource_id: str) -> Resource:
        """Get a resource by type and ID."""
        if resource_type not in self._resources:
            raise RegistryError(f"Unknown resource type '{resource_type}'")
        
        if resource_id not in self._resources[resource_type]:
            raise RegistryError(
                f"Resource '{resource_id}' of type '{resource_type}' not found"
            )
        return self._resources[resource_type][resource_id]
    
    def list_resources(self, resource_type: str) -> list[str]:
        """List all resource IDs of a given type."""
        if resource_type not in self._resources:
            return []
        return list(self._resources[resource_type].keys())
    
    # =========================================================================
    # Products
    # =========================================================================
    
    def register_product(self, product_id: str, config: dict[str, Any]) -> None:
        """Register a product definition."""
        if product_id in self._products:
            raise RegistryError(f"Product '{product_id}' is already registered")
        self._products[product_id] = config
    
    def get_product(self, product_id: str) -> dict[str, Any]:
        """Get a product definition by ID."""
        if product_id not in self._products:
            raise RegistryError(f"Product '{product_id}' not found")
        return self._products[product_id]
    
    def list_products(self) -> list[str]:
        """List all registered product IDs."""
        return list(self._products.keys())
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def validate_product(self, product_id: str) -> list[str]:
        """
        Validate that a product's dependencies are all registered.
        
        Returns a list of error messages (empty if valid).
        """
        errors: list[str] = []
        
        try:
            config = self.get_product(product_id)
        except RegistryError as e:
            return [str(e)]
        
        # Check resources
        resources = config.get("resources", {})
        for resource_type, resource_id in resources.items():
            if resource_type not in self._resources:
                errors.append(f"Unknown resource type '{resource_type}'")
            elif resource_id not in self._resources.get(resource_type, {}):
                errors.append(f"Resource '{resource_id}' of type '{resource_type}' not found")
        
        # Check collection interfaces
        collection = config.get("collection", {})
        for interface_id in collection.get("interfaces", []):
            if interface_id not in self._input_interfaces:
                errors.append(f"Input interface '{interface_id}' not found")
        
        # Check processing pipeline services
        processing = config.get("processing", {})
        for step in processing.get("pipeline", []):
            service_id = step.get("service") if isinstance(step, dict) else step
            if service_id not in self._services:
                errors.append(f"Service '{service_id}' not found")
        
        # Check delivery interfaces
        delivery = config.get("delivery", {})
        for interface_id in delivery.get("interfaces", []):
            if interface_id not in self._output_interfaces:
                errors.append(f"Output interface '{interface_id}' not found")
        
        return errors


# Singleton registry for the application
_default_registry: Registry | None = None


def get_registry() -> Registry:
    """Get the default registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = Registry()
    return _default_registry


def reset_registry() -> None:
    """Reset the default registry (useful for testing)."""
    global _default_registry
    _default_registry = None

