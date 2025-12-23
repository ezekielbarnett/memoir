"""
Phase Manager Service.

Manages the phased collection journey - initializing phases for contributors,
checking unlock conditions, and handling phase transitions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from memoir.core.events import Event
from memoir.core.models import (
    Contributor,
    PhaseProgress,
    PhaseStatus,
    utc_now,
)
from memoir.core.registry import get_registry
from memoir.products.loader import ProductDefinition, PhaseConfig
from memoir.services.base import Service


class PhaseManager(Service):
    """
    Manages phased collection journeys.
    
    Responsibilities:
    - Initialize phase progress for new contributors
    - Check and process phase unlocks (immediate, scheduled, on-completion)
    - Track phase completion
    - Emit events for phase state changes
    """
    
    @property
    def service_id(self) -> str:
        return "phase_manager"
    
    @property
    def subscribes_to(self) -> list[str]:
        return [
            "contributor.joined",  # Initialize phases for new contributor
            "content.created",  # Check if phase is complete
            "phase.check_unlock",  # Explicit check for scheduled unlocks
            "scheduler.tick",  # Periodic check for scheduled unlocks
        ]
    
    def __init__(self):
        self.registry = get_registry()
        # In-memory store for contributor data (would be DB in production)
        self._contributors: dict[str, Contributor] = {}
    
    async def handle(self, event: Event) -> list[Event]:
        """Handle phase-related events."""
        if event.event_type == "contributor.joined":
            return await self._handle_contributor_joined(event)
        elif event.event_type == "content.created":
            return await self._handle_content_created(event)
        elif event.event_type in ("phase.check_unlock", "scheduler.tick"):
            return await self._handle_check_unlocks(event)
        
        return []
    
    async def _handle_contributor_joined(self, event: Event) -> list[Event]:
        """Initialize phase progress when a contributor joins."""
        project_id = event.project_id
        contributor_id = event.contributor_id
        
        if not contributor_id:
            return []
        
        # Get product definition
        product = self._get_product_for_project(project_id)
        if not product or not product.is_phased:
            return []  # Non-phased product
        
        # Get or create contributor
        contributor = self._get_contributor(contributor_id)
        if not contributor:
            # Create a stub contributor for tracking
            contributor = Contributor(
                id=contributor_id,
                project_id=project_id,
                name=event.payload.get("name", "Unknown"),
            )
            self._contributors[contributor_id] = contributor
        
        # Initialize phase progress
        events = []
        now = utc_now()
        
        for phase in product.get_phases_in_order():
            progress = PhaseProgress(
                phase_id=phase.phase_id,
                status=PhaseStatus.LOCKED,
            )
            
            # Check if this phase should be immediately unlocked
            if phase.unlock.unlock_type == "immediate":
                progress.unlock()
                events.append(self._phase_unlocked_event(event, phase.phase_id))
            
            # For scheduled unlocks, calculate when it will unlock
            elif phase.unlock.unlock_type == "scheduled":
                if phase.unlock.requires_phase:
                    # Will be scheduled when required phase completes
                    pass
                else:
                    # Schedule from now
                    delay = phase.unlock.delay_days or 0
                    progress.scheduled_unlock_at = now + timedelta(days=delay)
            
            contributor.phase_progress[phase.phase_id] = progress
        
        # Set current phase to first available
        first_phase = product.get_first_phase()
        if first_phase and first_phase.unlock.unlock_type == "immediate":
            contributor.current_phase_id = first_phase.phase_id
        
        return events
    
    async def _handle_content_created(self, event: Event) -> list[Event]:
        """Check if adding content completes a phase."""
        contributor_id = event.contributor_id
        if not contributor_id:
            return []
        
        contributor = self._get_contributor(contributor_id)
        if not contributor:
            return []
        
        # Get current phase
        current_phase = contributor.get_current_phase()
        if not current_phase or current_phase.status != PhaseStatus.IN_PROGRESS:
            return []
        
        # Record the answer
        current_phase.record_answer()
        
        events = []
        
        # Check if phase is complete
        if current_phase.status == PhaseStatus.COMPLETED:
            events.append(self._phase_completed_event(event, current_phase.phase_id))
            
            # Check for phases that unlock on this completion
            events.extend(
                await self._check_completion_unlocks(event, contributor, current_phase.phase_id)
            )
            
            # Move to next available phase
            self._advance_to_next_phase(contributor, event.project_id)
        
        return events
    
    async def _handle_check_unlocks(self, event: Event) -> list[Event]:
        """Check for any scheduled phase unlocks that are due."""
        events = []
        now = utc_now()
        
        for contributor in self._contributors.values():
            for phase_id, progress in contributor.phase_progress.items():
                # Check scheduled unlocks
                if (
                    progress.status == PhaseStatus.LOCKED
                    and progress.scheduled_unlock_at
                    and progress.scheduled_unlock_at <= now
                ):
                    progress.unlock()
                    events.append(Event(
                        event_type="phase.unlocked",
                        project_id=contributor.project_id,
                        contributor_id=contributor.id,
                        payload={
                            "phase_id": phase_id,
                            "unlock_type": "scheduled",
                        },
                        correlation_id=event.correlation_id,
                        causation_id=event.id,
                    ))
                    
                    # Set as current if none set
                    if not contributor.current_phase_id:
                        contributor.current_phase_id = phase_id
        
        return events
    
    async def _check_completion_unlocks(
        self,
        event: Event,
        contributor: Contributor,
        completed_phase_id: str,
    ) -> list[Event]:
        """Check for phases that unlock when a phase is completed."""
        events = []
        
        product = self._get_product_for_project(contributor.project_id)
        if not product:
            return events
        
        now = utc_now()
        
        for phase in product.phases:
            progress = contributor.phase_progress.get(phase.phase_id)
            if not progress or progress.status != PhaseStatus.LOCKED:
                continue
            
            # Check if this phase requires the completed phase
            if phase.unlock.requires_phase != completed_phase_id:
                continue
            
            if phase.unlock.unlock_type == "on_completion":
                # Unlock immediately
                progress.unlock()
                events.append(self._phase_unlocked_event(event, phase.phase_id))
            
            elif phase.unlock.unlock_type == "scheduled":
                # Schedule unlock after delay
                delay = phase.unlock.delay_days or 0
                progress.scheduled_unlock_at = now + timedelta(days=delay)
                
                # Emit scheduled event for tracking
                events.append(Event(
                    event_type="phase.scheduled",
                    project_id=event.project_id,
                    contributor_id=contributor.id,
                    payload={
                        "phase_id": phase.phase_id,
                        "scheduled_for": progress.scheduled_unlock_at.isoformat(),
                        "delay_days": delay,
                    },
                    correlation_id=event.correlation_id,
                    causation_id=event.id,
                ))
        
        return events
    
    def _advance_to_next_phase(self, contributor: Contributor, project_id: str) -> None:
        """Move contributor to next available phase."""
        product = self._get_product_for_project(project_id)
        if not product:
            return
        
        # Find next available phase
        for phase in product.get_phases_in_order():
            progress = contributor.phase_progress.get(phase.phase_id)
            if progress and progress.status == PhaseStatus.AVAILABLE:
                contributor.current_phase_id = phase.phase_id
                return
        
        # No available phases - contributor is waiting or done
        contributor.current_phase_id = None
    
    def _phase_unlocked_event(self, parent: Event, phase_id: str) -> Event:
        """Create a phase.unlocked event."""
        return Event(
            event_type="phase.unlocked",
            project_id=parent.project_id,
            contributor_id=parent.contributor_id,
            payload={
                "phase_id": phase_id,
                "unlock_type": "immediate",
            },
            correlation_id=parent.correlation_id or parent.id,
            causation_id=parent.id,
        )
    
    def _phase_completed_event(self, parent: Event, phase_id: str) -> Event:
        """Create a phase.completed event."""
        return Event(
            event_type="phase.completed",
            project_id=parent.project_id,
            contributor_id=parent.contributor_id,
            payload={
                "phase_id": phase_id,
            },
            correlation_id=parent.correlation_id or parent.id,
            causation_id=parent.id,
        )
    
    def _get_product_for_project(self, project_id: str) -> ProductDefinition | None:
        """Get the product definition for a project."""
        # In production, this would look up the project's product_id
        # For now, we'll try to get it from the registry
        try:
            # This is a simplification - real impl would look up project first
            for product_id in self.registry.list_products():
                return ProductDefinition.from_dict(
                    self.registry.get_product(product_id)
                )
        except Exception:
            pass
        return None
    
    def _get_contributor(self, contributor_id: str) -> Contributor | None:
        """Get a contributor by ID."""
        return self._contributors.get(contributor_id)
    
    # =========================================================================
    # Public API for other services
    # =========================================================================
    
    def initialize_contributor(
        self,
        contributor: Contributor,
        product: ProductDefinition,
    ) -> list[str]:
        """
        Initialize phase progress for a contributor.
        
        Returns list of immediately unlocked phase IDs.
        """
        self._contributors[contributor.id] = contributor
        unlocked = []
        now = utc_now()
        
        for phase in product.get_phases_in_order():
            progress = PhaseProgress(
                phase_id=phase.phase_id,
                status=PhaseStatus.LOCKED,
            )
            
            if phase.unlock.unlock_type == "immediate":
                progress.unlock()
                unlocked.append(phase.phase_id)
            elif phase.unlock.unlock_type == "scheduled" and not phase.unlock.requires_phase:
                delay = phase.unlock.delay_days or 0
                progress.scheduled_unlock_at = now + timedelta(days=delay)
            
            contributor.phase_progress[phase.phase_id] = progress
        
        if unlocked:
            contributor.current_phase_id = unlocked[0]
        
        return unlocked
    
    def start_phase(self, contributor: Contributor, phase_id: str) -> bool:
        """
        Start a phase for a contributor.
        
        Returns True if successful, False if phase not available.
        """
        progress = contributor.phase_progress.get(phase_id)
        if not progress or progress.status != PhaseStatus.AVAILABLE:
            return False
        
        progress.start()
        contributor.current_phase_id = phase_id
        return True
    
    def get_contributor_status(
        self,
        contributor: Contributor,
        product: ProductDefinition,
    ) -> dict[str, Any]:
        """Get a summary of contributor's phase progress."""
        phases_status = []
        
        for phase in product.get_phases_in_order():
            progress = contributor.phase_progress.get(phase.phase_id)
            phases_status.append({
                "phase_id": phase.phase_id,
                "name": phase.name,
                "status": progress.status.value if progress else "unknown",
                "questions_answered": progress.questions_answered if progress else 0,
                "questions_total": progress.questions_total if progress else None,
                "scheduled_unlock": (
                    progress.scheduled_unlock_at.isoformat()
                    if progress and progress.scheduled_unlock_at
                    else None
                ),
            })
        
        return {
            "current_phase": contributor.current_phase_id,
            "phases": phases_status,
            "completed_count": len(contributor.get_completed_phases()),
            "total_phases": len(product.phases),
        }

