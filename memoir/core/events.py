"""
Event system for memoir platform.

The event bus is the nervous system of the platform. Components emit events
and subscribe to events they care about, enabling loose coupling and scalability.
"""

from __future__ import annotations

import asyncio
import fnmatch
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

# Type for event handlers
EventHandler = Callable[["Event"], Awaitable[list["Event"]]]


@dataclass
class Event:
    """
    An event in the system.
    
    Events are immutable records of something that happened. They carry
    all the context needed for handlers to process them.
    """
    
    event_type: str  # e.g., "content.created", "question.selected"
    project_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    
    # Optional context
    contributor_id: str | None = None
    
    # Tracing
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None  # Groups related events
    causation_id: str | None = None  # Event that caused this one
    
    # Timing
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def caused_by(self, parent: Event) -> Event:
        """Create a child event caused by this one, inheriting correlation."""
        return Event(
            event_type=self.event_type,
            project_id=self.project_id,
            payload=self.payload,
            contributor_id=self.contributor_id,
            correlation_id=parent.correlation_id or parent.id,
            causation_id=parent.id,
        )
    
    def with_correlation(self, correlation_id: str) -> Event:
        """Return a copy with the specified correlation ID."""
        return Event(
            event_type=self.event_type,
            project_id=self.project_id,
            payload=self.payload,
            contributor_id=self.contributor_id,
            id=self.id,
            correlation_id=correlation_id,
            causation_id=self.causation_id,
            timestamp=self.timestamp,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "project_id": self.project_id,
            "contributor_id": self.contributor_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize event from dictionary."""
        return cls(
            id=data["id"],
            event_type=data["event_type"],
            project_id=data["project_id"],
            contributor_id=data.get("contributor_id"),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class Subscription:
    """A subscription to events matching a pattern."""
    
    pattern: str  # e.g., "content.*" or "question.selected"
    handler: EventHandler
    filter: dict[str, Any] = field(default_factory=dict)  # Additional filters
    
    def matches(self, event: Event) -> bool:
        """Check if this subscription matches the given event."""
        # Check pattern match (supports wildcards like "content.*")
        if not fnmatch.fnmatch(event.event_type, self.pattern):
            return False
        
        # Check additional filters
        for key, value in self.filter.items():
            if key == "project_id" and event.project_id != value:
                return False
            if key == "contributor_id" and event.contributor_id != value:
                return False
            # Check payload filters
            if key.startswith("payload."):
                payload_key = key[8:]
                if event.payload.get(payload_key) != value:
                    return False
        
        return True


class EventBus:
    """
    In-memory event bus implementation.
    
    This is suitable for development and single-instance deployment.
    For production at scale, this can be swapped for Redis pub/sub,
    Kafka, or AWS EventBridge.
    """
    
    def __init__(self):
        self._subscriptions: list[Subscription] = []
        self._event_history: list[Event] = []
        self._max_history = 10000
        self._middlewares: list[Callable[[Event], Event | None]] = []
    
    def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        filter: dict[str, Any] | None = None,
    ) -> Subscription:
        """
        Subscribe to events matching a pattern.
        
        Args:
            pattern: Event type pattern (supports wildcards like "content.*")
            handler: Async function to handle matching events
            filter: Additional filters (e.g., {"project_id": "proj_123"})
        
        Returns:
            The subscription object (can be used to unsubscribe)
        """
        subscription = Subscription(
            pattern=pattern,
            handler=handler,
            filter=filter or {},
        )
        self._subscriptions.append(subscription)
        return subscription
    
    def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a subscription."""
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)
    
    def add_middleware(self, middleware: Callable[[Event], Event | None]) -> None:
        """
        Add middleware that processes events before they're dispatched.
        
        Middleware can modify events or return None to drop them.
        """
        self._middlewares.append(middleware)
    
    async def publish(self, event: Event) -> list[Event]:
        """
        Publish an event and return any events produced by handlers.
        
        This implements a simple event cascade: handlers can return new events,
        which are then also published.
        """
        # Run through middleware
        current_event: Event | None = event
        for middleware in self._middlewares:
            if current_event is None:
                return []
            current_event = middleware(current_event)
        
        if current_event is None:
            return []
        
        # Store in history
        self._event_history.append(current_event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # Find matching subscriptions
        matching = [s for s in self._subscriptions if s.matches(current_event)]
        
        # Execute handlers and collect resulting events
        all_resulting_events: list[Event] = []
        
        for subscription in matching:
            try:
                resulting_events = await subscription.handler(current_event)
                all_resulting_events.extend(resulting_events)
            except Exception as e:
                # Log error but don't stop other handlers
                print(f"Error in event handler for {current_event.event_type}: {e}")
        
        # Recursively publish resulting events
        for resulting_event in all_resulting_events:
            cascade_events = await self.publish(resulting_event)
            all_resulting_events.extend(cascade_events)
        
        return all_resulting_events
    
    async def publish_many(self, events: list[Event]) -> list[Event]:
        """Publish multiple events and return all resulting events."""
        all_results: list[Event] = []
        for event in events:
            results = await self.publish(event)
            all_results.extend(results)
        return all_results
    
    def get_history(
        self,
        event_type: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query event history with optional filters."""
        results = self._event_history
        
        if event_type:
            results = [e for e in results if fnmatch.fnmatch(e.event_type, event_type)]
        
        if project_id:
            results = [e for e in results if e.project_id == project_id]
        
        return results[-limit:]


# Singleton event bus for the application
_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the default event bus instance."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_event_bus() -> None:
    """Reset the default event bus (useful for testing)."""
    global _default_bus
    _default_bus = None


# Convenience functions for common event types
def content_created(
    project_id: str,
    content_id: str,
    contributor_id: str,
    content_type: str,
    **extra_payload,
) -> Event:
    """Create a content.created event."""
    return Event(
        event_type="content.created",
        project_id=project_id,
        contributor_id=contributor_id,
        payload={
            "content_id": content_id,
            "content_type": content_type,
            **extra_payload,
        },
    )


def question_requested(
    project_id: str,
    contributor_id: str,
    **extra_payload,
) -> Event:
    """Create a question.requested event."""
    return Event(
        event_type="question.requested",
        project_id=project_id,
        contributor_id=contributor_id,
        payload=extra_payload,
    )


def question_selected(
    project_id: str,
    contributor_id: str,
    question_id: str,
    question_text: str,
    **extra_payload,
) -> Event:
    """Create a question.selected event."""
    return Event(
        event_type="question.selected",
        project_id=project_id,
        contributor_id=contributor_id,
        payload={
            "question_id": question_id,
            "question_text": question_text,
            **extra_payload,
        },
    )


def processing_started(project_id: str, pipeline: list[str], **extra_payload) -> Event:
    """Create a processing.started event."""
    return Event(
        event_type="processing.started",
        project_id=project_id,
        payload={
            "pipeline": pipeline,
            **extra_payload,
        },
    )


def processing_complete(project_id: str, **extra_payload) -> Event:
    """Create a processing.complete event."""
    return Event(
        event_type="processing.complete",
        project_id=project_id,
        payload=extra_payload,
    )

