"""
Core data models for the memoir platform.

These models represent the fundamental entities: Projects, Contributors,
and Content Items. All are designed with full provenance tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from memoir.core.utils import generate_id, utc_now


# =============================================================================
# Enums
# =============================================================================


class ProjectStatus(str, Enum):
    """Status of a memoir project."""
    
    DRAFT = "draft"  # Just created, not yet collecting
    COLLECTING = "collecting"  # Actively collecting content
    PROCESSING = "processing"  # Running through pipeline
    REVIEW = "review"  # Ready for human review
    COMPLETE = "complete"  # Finished
    ARCHIVED = "archived"  # No longer active


class ContributorStatus(str, Enum):
    """Status of a contributor."""
    
    INVITED = "invited"  # Invitation sent, not yet accepted
    ACTIVE = "active"  # Actively contributing
    COMPLETED = "completed"  # Finished contributing
    DECLINED = "declined"  # Declined invitation


class ContributorRole(str, Enum):
    """Role of a contributor in the life story."""
    
    SUBJECT = "subject"        # The person whose story this is
    FAMILY = "family"          # Family member (child, sibling, spouse, etc.)
    FRIEND = "friend"          # Close friend
    COLLEAGUE = "colleague"    # Work colleague
    CAREGIVER = "caregiver"    # Professional caregiver
    INTERVIEWER = "interviewer"  # Professional interviewer/biographer


class PhaseStatus(str, Enum):
    """Status of a contributor's progress in a phase."""
    
    LOCKED = "locked"  # Phase not yet unlocked
    AVAILABLE = "available"  # Unlocked but not started
    IN_PROGRESS = "in_progress"  # Started but not complete
    COMPLETED = "completed"  # All questions answered


class ContentType(str, Enum):
    """Types of content that can be collected."""
    
    TEXT = "text"  # Plain text
    STRUCTURED_QA = "structured_qa"  # Question-answer pair
    IMAGE = "image"  # Photo with optional description
    AUDIO = "audio"  # Audio recording (pre-transcription)
    DOCUMENT = "document"  # Uploaded document


# =============================================================================
# Subject (who/what the memoir is about)
# =============================================================================


class Subject(BaseModel):
    """The subject of a memoir project."""
    
    name: str
    birth_date: datetime | None = None
    photo_url: str | None = None
    additional_info: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Project
# =============================================================================


class Project(BaseModel):
    """
    A memoir project - the top-level container.
    
    A project belongs to an owner, is about a subject, and collects
    content from multiple contributors.
    """
    
    id: str = Field(default_factory=lambda: generate_id("proj"))
    
    # Basic info
    name: str
    description: str = ""
    
    # What product definition this uses
    product_id: str
    
    # Ownership
    owner_id: str  # User who created and controls this project
    
    # Subject
    subject: Subject
    
    # State
    status: ProjectStatus = ProjectStatus.DRAFT
    
    # Product-specific settings (overrides from product definition)
    settings: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    # Optional deadline
    deadline: datetime | None = None
    
    def update(self, **kwargs) -> None:
        """Update fields and set updated_at."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = utc_now()


# =============================================================================
# Phase Progress (tracks contributor's journey through phases)
# =============================================================================


class PhaseProgress(BaseModel):
    """Tracks a contributor's progress through a single phase."""
    
    phase_id: str
    status: PhaseStatus = PhaseStatus.LOCKED
    
    # When this phase became available/unlocked
    unlocked_at: datetime | None = None
    
    # When the contributor started this phase
    started_at: datetime | None = None
    
    # When the contributor completed this phase
    completed_at: datetime | None = None
    
    # Progress tracking
    questions_answered: int = 0
    questions_total: int | None = None  # Set when phase is initialized
    
    # For scheduled unlocks - when the phase WILL unlock
    scheduled_unlock_at: datetime | None = None
    
    def unlock(self) -> None:
        """Mark this phase as unlocked/available."""
        self.status = PhaseStatus.AVAILABLE
        self.unlocked_at = utc_now()
    
    def start(self) -> None:
        """Mark this phase as started."""
        if self.status == PhaseStatus.AVAILABLE:
            self.status = PhaseStatus.IN_PROGRESS
            self.started_at = utc_now()
    
    def complete(self) -> None:
        """Mark this phase as completed."""
        self.status = PhaseStatus.COMPLETED
        self.completed_at = utc_now()
    
    def record_answer(self) -> None:
        """Record that a question was answered."""
        self.questions_answered += 1
        if self.questions_total and self.questions_answered >= self.questions_total:
            self.complete()


# =============================================================================
# Contributor
# =============================================================================


class Contributor(BaseModel):
    """
    A contributor to a project.
    
    Contributors can be registered users or anonymous (via invite link).
    Every piece of content is traced back to a contributor.
    """
    
    id: str = Field(default_factory=lambda: generate_id("contrib"))
    
    # Which project
    project_id: str
    
    # Identity (user_id is None for anonymous contributors)
    user_id: str | None = None
    name: str
    email: str | None = None
    
    # Role and relationship to subject
    role: ContributorRole = ContributorRole.FAMILY
    relationship: str | None = None  # Specific: "daughter", "grandson", "best friend", etc.
    
    # Access control
    permissions: list[str] = Field(default_factory=lambda: ["contribute"])
    invite_token: str | None = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # State
    status: ContributorStatus = ContributorStatus.INVITED
    
    # Phase tracking
    current_phase_id: str | None = None
    phase_progress: dict[str, PhaseProgress] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    last_activity_at: datetime | None = None
    
    def record_activity(self) -> None:
        """Record that this contributor was active."""
        self.last_activity_at = utc_now()
    
    def get_phase_progress(self, phase_id: str) -> PhaseProgress | None:
        """Get progress for a specific phase."""
        return self.phase_progress.get(phase_id)
    
    def get_current_phase(self) -> PhaseProgress | None:
        """Get the current phase progress."""
        if self.current_phase_id:
            return self.phase_progress.get(self.current_phase_id)
        return None
    
    def get_available_phases(self) -> list[PhaseProgress]:
        """Get all phases that are available or in progress."""
        return [
            p for p in self.phase_progress.values()
            if p.status in (PhaseStatus.AVAILABLE, PhaseStatus.IN_PROGRESS)
        ]
    
    def get_completed_phases(self) -> list[PhaseProgress]:
        """Get all completed phases."""
        return [
            p for p in self.phase_progress.values()
            if p.status == PhaseStatus.COMPLETED
        ]


# =============================================================================
# Content Item
# =============================================================================


class TextContent(BaseModel):
    """Text content payload."""
    
    text: str
    language: str = "en"


class StructuredQAContent(BaseModel):
    """Question-answer content payload."""
    
    question_id: str
    question_text: str
    answer_text: str
    language: str = "en"


class ImageContent(BaseModel):
    """Image content payload."""
    
    url: str
    description: str | None = None
    ocr_text: str | None = None
    width: int | None = None
    height: int | None = None


class AudioContent(BaseModel):
    """Audio content payload."""
    
    url: str
    duration_seconds: float | None = None
    transcription_content_id: str | None = None  # Link to transcribed version


class DocumentContent(BaseModel):
    """Document content payload."""
    
    url: str
    filename: str
    mime_type: str
    extracted_text: str | None = None


# Union of all content types
ContentPayload = TextContent | StructuredQAContent | ImageContent | AudioContent | DocumentContent


class ContentItem(BaseModel):
    """
    A single piece of content with full provenance.
    
    Content items are the atoms of the system. They are immutable
    after creation (new versions create new items linked to previous).
    """
    
    id: str = Field(default_factory=lambda: generate_id("content"))
    
    # Ownership
    project_id: str
    contributor_id: str
    
    # Content
    content_type: ContentType
    content: dict[str, Any]  # Type-specific payload
    
    # Provenance
    source_interface: str  # "voice_recorder", "web_form", etc.
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Organization
    tags: list[str] = Field(default_factory=list)
    question_id: str | None = None  # If in response to a question
    
    # Versioning
    version: int = 1
    previous_version_id: str | None = None
    
    # Processing state
    is_processed: bool = False
    processing_metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    
    def create_new_version(self, **content_updates) -> ContentItem:
        """Create a new version of this content item."""
        new_content = self.content.copy()
        new_content.update(content_updates)
        
        return ContentItem(
            project_id=self.project_id,
            contributor_id=self.contributor_id,
            content_type=self.content_type,
            content=new_content,
            source_interface=self.source_interface,
            source_metadata=self.source_metadata,
            tags=self.tags.copy(),
            question_id=self.question_id,
            version=self.version + 1,
            previous_version_id=self.id,
        )


# =============================================================================
# User (for authentication - can be expanded)
# =============================================================================


class User(BaseModel):
    """
    A registered user of the platform.
    
    Users can own projects and be contributors.
    """
    
    id: str = Field(default_factory=lambda: generate_id("user"))
    email: str
    name: str
    
    # Auth (simplified - expand as needed)
    password_hash: str | None = None
    is_active: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    last_login_at: datetime | None = None



