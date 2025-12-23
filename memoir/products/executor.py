"""
Product executor.

The executor runs a product definition - it orchestrates the flow
of events through the system based on the product configuration.
"""

from __future__ import annotations

from typing import Any

from memoir.core.events import Event, EventBus, get_event_bus
from memoir.core.models import (
    Project,
    Contributor,
    ContentItem,
    Subject,
    ProjectStatus,
    ContributorStatus,
    ContentType,
)
from memoir.core.projections import (
    DocumentProjection,
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    UpdateMode,
)
from memoir.core.registry import Registry, get_registry
from memoir.products.loader import ProductDefinition, ProductLoader


class ProductExecutor:
    """
    Executes a product definition.
    
    The executor is responsible for:
    1. Creating projects based on a product definition
    2. Managing contributors
    3. Orchestrating content collection
    4. Managing document projections
    """
    
    def __init__(
        self,
        registry: Registry | None = None,
        event_bus: EventBus | None = None,
    ):
        self.registry = registry or get_registry()
        self.event_bus = event_bus or get_event_bus()
        self.product_loader = ProductLoader(self.registry)
        
        # In-memory stores (replace with persistent storage)
        self._projects: dict[str, Project] = {}
        self._contributors: dict[str, dict[str, Contributor]] = {}  # project_id -> contributors
        self._content: dict[str, list[ContentItem]] = {}  # project_id -> content items
        self._projections: dict[str, dict[str, DocumentProjection]] = {}  # project_id -> projections
    
    # =========================================================================
    # Project Management
    # =========================================================================
    
    async def create_project(
        self,
        product_id: str,
        name: str,
        owner_id: str,
        subject_name: str,
        subject_data: dict[str, Any] | None = None,
    ) -> Project:
        """
        Create a new project using a product definition.
        
        Args:
            product_id: Which product to use
            name: Project name
            owner_id: User creating the project
            subject_name: Name of the memoir subject
            subject_data: Additional subject data
        """
        # Get product definition
        product = self.product_loader.get_product(product_id)
        
        # Create subject
        subject = Subject(
            name=subject_name,
            **(subject_data or {}),
        )
        
        # Create project
        project = Project(
            name=name,
            product_id=product_id,
            owner_id=owner_id,
            subject=subject,
            status=ProjectStatus.DRAFT,
        )
        
        # Store
        self._projects[project.id] = project
        self._contributors[project.id] = {}
        self._content[project.id] = []
        self._projections[project.id] = {}
        
        # Emit event
        await self.event_bus.publish(Event(
            event_type="project.created",
            project_id=project.id,
            payload={
                "name": name,
                "product_id": product_id,
                "owner_id": owner_id,
                "subject": subject.model_dump(),
            },
        ))
        
        # Add owner as contributor
        await self.add_contributor(
            project_id=project.id,
            user_id=owner_id,
            name="Owner",
            relationship="owner",
            permissions=["contribute", "manage", "export"],
        )
        
        return project
    
    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)
    
    async def update_project_status(
        self,
        project_id: str,
        status: ProjectStatus,
    ) -> Project:
        """Update a project's status."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        old_status = project.status
        project.status = status
        project.update()
        
        await self.event_bus.publish(Event(
            event_type="project.status_changed",
            project_id=project_id,
            payload={
                "old_status": old_status.value,
                "new_status": status.value,
            },
        ))
        
        return project
    
    async def start_collection(self, project_id: str) -> Project:
        """Move project to collecting status."""
        return await self.update_project_status(project_id, ProjectStatus.COLLECTING)
    
    # =========================================================================
    # Contributor Management
    # =========================================================================
    
    async def add_contributor(
        self,
        project_id: str,
        name: str,
        user_id: str | None = None,
        email: str | None = None,
        relationship: str | None = None,
        permissions: list[str] | None = None,
    ) -> Contributor:
        """Add a contributor to a project."""
        if project_id not in self._contributors:
            raise ValueError(f"Project {project_id} not found")
        
        contributor = Contributor(
            project_id=project_id,
            user_id=user_id,
            name=name,
            email=email,
            relationship=relationship,
            permissions=permissions or ["contribute"],
            status=ContributorStatus.ACTIVE if user_id else ContributorStatus.INVITED,
        )
        
        self._contributors[project_id][contributor.id] = contributor
        
        await self.event_bus.publish(Event(
            event_type="contributor.joined",
            project_id=project_id,
            contributor_id=contributor.id,
            payload={
                "name": name,
                "relationship": relationship,
                "invite_token": contributor.invite_token,
            },
        ))
        
        return contributor
    
    def get_contributor(self, project_id: str, contributor_id: str) -> Contributor | None:
        """Get a contributor by ID."""
        return self._contributors.get(project_id, {}).get(contributor_id)
    
    def get_contributor_by_token(self, project_id: str, token: str) -> Contributor | None:
        """Get a contributor by invite token."""
        for contributor in self._contributors.get(project_id, {}).values():
            if contributor.invite_token == token:
                return contributor
        return None
    
    def list_contributors(self, project_id: str) -> list[Contributor]:
        """List all contributors for a project."""
        return list(self._contributors.get(project_id, {}).values())
    
    # =========================================================================
    # Content Collection
    # =========================================================================
    
    async def request_question(
        self,
        project_id: str,
        contributor_id: str,
    ) -> Event:
        """Request the next question for a contributor."""
        event = Event(
            event_type="question.requested",
            project_id=project_id,
            contributor_id=contributor_id,
            payload={
                "answered_count": len(self.get_contributor_content(project_id, contributor_id)),
            },
        )
        
        # This will trigger QuestionSelector service (when registered)
        await self.event_bus.publish(event)
        
        return event
    
    async def add_content(
        self,
        project_id: str,
        contributor_id: str,
        content_type: str,
        content: dict[str, Any],
        source_interface: str,
        question_id: str | None = None,
        tags: list[str] | None = None,
    ) -> ContentItem:
        """Add a content item to a project."""
        if project_id not in self._content:
            raise ValueError(f"Project {project_id} not found")
        
        item = ContentItem(
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType(content_type),
            content=content,
            source_interface=source_interface,
            question_id=question_id,
            tags=tags or [],
        )
        
        self._content[project_id].append(item)
        
        # Update contributor activity
        contributor = self.get_contributor(project_id, contributor_id)
        if contributor:
            contributor.record_activity()
        
        await self.event_bus.publish(Event(
            event_type="content.created",
            project_id=project_id,
            contributor_id=contributor_id,
            payload={
                "content_id": item.id,
                "content_type": content_type,
                "source_interface": source_interface,
                "question_id": question_id,
            },
        ))
        
        return item
    
    def get_content(self, project_id: str) -> list[ContentItem]:
        """Get all content for a project."""
        return self._content.get(project_id, [])
    
    def get_contributor_content(
        self,
        project_id: str,
        contributor_id: str,
    ) -> list[ContentItem]:
        """Get all content from a specific contributor."""
        return [
            item for item in self._content.get(project_id, [])
            if item.contributor_id == contributor_id
        ]
    
    # =========================================================================
    # Projection Management
    # =========================================================================
    
    async def create_projection(
        self,
        project_id: str,
        name: str = "Document",
        style: str = "thematic",
        length: str = "standard",
        suggested_sections: list[str] | None = None,
    ) -> Event:
        """
        Create a new document projection for a project.
        
        This emits a projection.generate event that the ProjectionService handles.
        """
        event = Event(
            event_type="projection.generate",
            project_id=project_id,
            payload={
                "name": name,
                "config": {
                    "style": style,
                    "length": length,
                    "suggested_sections": suggested_sections,
                },
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    async def update_projection(
        self,
        project_id: str,
        projection_id: str,
        mode: str = "evolve",
        section_ids: list[str] | None = None,
    ) -> Event:
        """
        Update a projection with new content.
        
        Modes:
        - evolve: Integrate new content while preserving structure
        - regenerate: Fully regenerate unlocked sections
        - refresh: Only update stale sections
        - append: Add new content to existing sections
        """
        event = Event(
            event_type="projection.update",
            project_id=project_id,
            payload={
                "projection_id": projection_id,
                "mode": mode,
                "section_ids": section_ids,
            },
        )
        
        await self.event_bus.publish(event)
        return event
    
    # =========================================================================
    # Event Wiring
    # =========================================================================
    
    def wire_services(self) -> None:
        """
        Wire all registered services to the event bus.
        
        This connects each service's handle method to its subscribed events.
        """
        for service_id in self.registry.list_services():
            service = self.registry.get_service(service_id)
            
            for pattern in service.subscribes_to:
                self.event_bus.subscribe(pattern, service.handle)
