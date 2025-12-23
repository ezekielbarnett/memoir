"""
Base class for all services.

Services are stateless transformations that handle events and produce
new events. They're the workhorses of the system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from memoir.core.events import Event


class Service(ABC):
    """
    Base class for all services.
    
    Services are stateless components that:
    1. Subscribe to specific event types
    2. Process those events
    3. Emit new events as a result
    
    Example:
        class TranscriptionService(Service):
            service_id = "transcription"
            subscribes_to = ["audio.uploaded"]
            
            async def handle(self, event: Event) -> list[Event]:
                audio_url = event.payload["audio_url"]
                text = await self.transcribe(audio_url)
                return [Event(
                    event_type="content.created",
                    project_id=event.project_id,
                    contributor_id=event.contributor_id,
                    payload={"content_type": "text", "text": text}
                )]
    """
    
    @property
    @abstractmethod
    def service_id(self) -> str:
        """Unique identifier for this service."""
        pass
    
    @property
    @abstractmethod
    def subscribes_to(self) -> list[str]:
        """
        List of event patterns this service handles.
        
        Supports wildcards like "content.*" or "question.selected".
        """
        pass
    
    @abstractmethod
    async def handle(self, event: Event) -> list[Event]:
        """
        Handle an event and return any resulting events.
        
        Args:
            event: The event to process
            
        Returns:
            List of events produced by handling this event
            (can be empty if no follow-up events needed)
        """
        pass
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """
        Initialize the service with configuration.
        
        Override this to set up any resources the service needs.
        Called once when the service is registered.
        """
        pass
    
    async def shutdown(self) -> None:
        """
        Clean up resources when the service is being shut down.
        
        Override this to release any resources.
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.service_id})>"


class ConfigurableService(Service):
    """
    A service that can be configured per-invocation.
    
    Use this when the same service logic needs different settings
    for different products or contexts.
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
    
    @property
    def config(self) -> dict[str, Any]:
        """Get the current configuration."""
        return self._config
    
    def with_config(self, config: dict[str, Any]) -> ConfigurableService:
        """
        Create a new instance with merged configuration.
        
        This allows product definitions to override default settings.
        """
        merged = {**self._config, **config}
        return self.__class__(merged)


class PipelineService(Service):
    """
    A service designed to run as part of a processing pipeline.
    
    Pipeline services implement a simpler interface focused on
    transforming content rather than handling arbitrary events.
    """
    
    @property
    def subscribes_to(self) -> list[str]:
        # Pipeline services are invoked directly, not via events
        return []
    
    async def handle(self, event: Event) -> list[Event]:
        # Default implementation for event handling
        # Pipeline services are typically called via process() instead
        return []
    
    @abstractmethod
    async def process(
        self,
        content_items: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Process content items and return transformed items.
        
        Args:
            content_items: List of content items to process
            context: Additional context (project settings, etc.)
            
        Returns:
            Transformed content items
        """
        pass

