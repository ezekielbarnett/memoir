"""
Document Projections - Documents as computed views of content.

The core insight: content is primary, documents are projections.
- ContentPool holds all raw content (source of truth)
- DocumentProjection is a computed view that can be regenerated
- Sections can be locked to preserve work
- Documents are versioned and support incremental updates

This enables:
- Multiple views of the same content (chronological, thematic, summary)
- Continuous document evolution as content arrives
- Manual editing without losing AI capabilities
- Multi-contributor documents that merge naturally
- Version history with ability to compare/revert
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from memoir.core.utils import generate_id, utc_now


# =============================================================================
# Section States
# =============================================================================


class SectionState(str, Enum):
    """State of a section in a projection."""
    
    # AI-generated, will regenerate when content changes or on request
    GENERATED = "generated"
    
    # User has approved this version - won't change unless explicitly unlocked
    LOCKED = "locked"
    
    # User is actively editing - hands off
    DRAFT = "draft"
    
    # Placeholder - no content yet, waiting for relevant content
    EMPTY = "empty"


class UpdateMode(str, Enum):
    """How to update a projection when new content arrives."""
    
    # Full regeneration of unlocked sections
    REGENERATE = "regenerate"
    
    # Evolve existing content - integrate new info while preserving structure
    EVOLVE = "evolve"
    
    # Append new content to existing sections
    APPEND = "append"
    
    # Only update if section is stale (content changed since last generation)
    REFRESH = "refresh"


# =============================================================================
# Narrative Context - AI memory for coherent storytelling
# =============================================================================


class DiscoveredTheme(BaseModel):
    """A theme discovered from the content."""
    
    theme: str  # e.g., "close family bonds"
    description: str = ""  # Longer description
    evidence: list[str] = Field(default_factory=list)  # Content snippets supporting this
    strength: float = 1.0  # How strongly this theme appears (0-1)
    source_content_ids: list[str] = Field(default_factory=list)  # Which content items


class NarrativeContext(BaseModel):
    """
    AI-generated context that informs future interactions.
    
    This is updated as content is added, giving the AI "memory" of
    what's been discussed. This enables more relevant questions and
    more cohesive writing.
    """
    
    # Summary of the story so far
    summary: str = ""
    
    # Key facts extracted
    key_facts: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"birthplace": "rural Ohio", "siblings": 2, "childhood_tone": "happy"}
    
    # Themes discovered
    themes: list[DiscoveredTheme] = Field(default_factory=list)
    
    # Suggested areas to explore
    suggested_topics: list[str] = Field(default_factory=list)
    
    # Questions to avoid (already well-covered)
    covered_topics: list[str] = Field(default_factory=list)
    
    # Emotional tone detected
    emotional_tone: str = "neutral"  # warm, nostalgic, reflective, etc.
    
    # Writing style notes
    voice_notes: str = ""  # "Uses humor, tends toward understatement"
    
    # Last updated
    updated_at: datetime = Field(default_factory=utc_now)
    
    def add_theme(self, theme: DiscoveredTheme) -> None:
        """Add or update a theme."""
        for existing in self.themes:
            if existing.theme.lower() == theme.theme.lower():
                # Merge evidence and update strength
                existing.evidence.extend(theme.evidence)
                existing.source_content_ids.extend(theme.source_content_ids)
                existing.strength = min(1.0, existing.strength + 0.1)
                return
        self.themes.append(theme)
    
    def update(self) -> None:
        """Mark as updated."""
        self.updated_at = utc_now()


# =============================================================================
# Section Version History
# =============================================================================


class SectionVersion(BaseModel):
    """A historical version of a section."""
    
    version: int
    content: str
    summary: str = ""
    
    # What triggered this version
    trigger: str = "generation"  # generation, regeneration, evolution, manual_edit
    
    # What content was used
    source_content_ids: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = None  # user_id if manual, None if AI


# =============================================================================
# Projected Section
# =============================================================================


class ProjectedSection(BaseModel):
    """
    A section within a document projection.
    
    Sections can be in different states:
    - GENERATED: AI created, will regenerate as content evolves
    - LOCKED: User approved, frozen until explicitly unlocked
    - DRAFT: User editing, don't touch
    - EMPTY: Waiting for content
    
    Sections maintain version history for tracking changes.
    """
    
    id: str = Field(default_factory=lambda: generate_id("sec"))
    
    # Content
    title: str
    content: str = ""
    summary: str = ""  # Brief summary for navigation
    
    # What content items contributed to this section
    source_content_ids: list[str] = Field(default_factory=list)
    
    # Who contributed to this section
    contributor_ids: list[str] = Field(default_factory=list)
    primary_contributor_id: str | None = None  # Main voice in this section
    
    # State management
    state: SectionState = SectionState.EMPTY
    
    # Generation metadata
    generated_at: datetime | None = None
    generation_prompt: str | None = None
    generation_config: dict[str, Any] = Field(default_factory=dict)
    
    # Lock metadata
    locked_at: datetime | None = None
    locked_by: str | None = None  # user_id who locked it
    lock_reason: str | None = None  # "approved", "manually edited", etc.
    
    # Ordering
    order: int = 0
    
    # Version history
    version: int = 1
    history: list[SectionVersion] = Field(default_factory=list)
    
    # Staleness tracking - which content IDs have been seen
    last_content_snapshot: list[str] = Field(default_factory=list)
    
    def lock(self, user_id: str, reason: str = "approved") -> None:
        """Lock this section to prevent regeneration."""
        self.state = SectionState.LOCKED
        self.locked_at = utc_now()
        self.locked_by = user_id
        self.lock_reason = reason
    
    def unlock(self) -> None:
        """Unlock section, allowing regeneration."""
        self.state = SectionState.GENERATED
        self.locked_at = None
        self.locked_by = None
        self.lock_reason = None
    
    def start_editing(self) -> None:
        """Mark section as being edited by user."""
        self.state = SectionState.DRAFT
    
    def finish_editing(self, new_content: str, lock: bool = False, user_id: str | None = None) -> None:
        """Complete editing and optionally lock."""
        # Save current version to history
        self._save_to_history("manual_edit", user_id)
        
        self.content = new_content
        self.version += 1
        
        if lock:
            self.state = SectionState.LOCKED
            self.locked_at = utc_now()
            self.locked_by = user_id
            self.lock_reason = "manually edited"
        else:
            self.state = SectionState.GENERATED
    
    def update_content(
        self,
        new_content: str,
        source_content_ids: list[str],
        trigger: str = "generation",
    ) -> None:
        """
        Update section content, saving history.
        
        Args:
            new_content: The new content
            source_content_ids: Content items used in generation
            trigger: What caused the update (generation, evolution, etc.)
        """
        # Save current to history if we have content
        if self.content:
            self._save_to_history(trigger)
        
        self.content = new_content
        self.source_content_ids = source_content_ids
        self.last_content_snapshot = source_content_ids.copy()
        self.generated_at = utc_now()
        self.state = SectionState.GENERATED
        self.version += 1
    
    def _save_to_history(self, trigger: str, user_id: str | None = None) -> None:
        """Save current content to history."""
        if not self.content:
            return
            
        self.history.append(SectionVersion(
            version=self.version,
            content=self.content,
            summary=self.summary,
            trigger=trigger,
            source_content_ids=self.source_content_ids.copy(),
            created_by=user_id,
        ))
        
        # Keep only last 10 versions
        if len(self.history) > 10:
            self.history = self.history[-10:]
    
    def revert_to_version(self, version: int) -> bool:
        """Revert to a previous version."""
        for hist in self.history:
            if hist.version == version:
                self._save_to_history("revert")
                self.content = hist.content
                self.summary = hist.summary
                self.source_content_ids = hist.source_content_ids.copy()
                self.version += 1
                return True
        return False
    
    def is_stale(self, current_content_ids: list[str]) -> bool:
        """Check if section is stale (new content available)."""
        current_set = set(current_content_ids)
        snapshot_set = set(self.last_content_snapshot)
        return current_set != snapshot_set
    
    @property
    def is_locked(self) -> bool:
        return self.state == SectionState.LOCKED
    
    @property
    def can_regenerate(self) -> bool:
        return self.state in (SectionState.GENERATED, SectionState.EMPTY)


# =============================================================================
# Projection Configuration
# =============================================================================


class ProjectionStyle(str, Enum):
    """How to structure the projection."""
    
    CHRONOLOGICAL = "chronological"  # Time-ordered narrative
    THEMATIC = "thematic"  # Grouped by themes AI discovers
    BY_CONTRIBUTOR = "by_contributor"  # Each person's contributions
    QUESTIONS = "questions"  # Organized by questions asked
    FREEFORM = "freeform"  # AI decides entirely


class ProjectionLength(str, Enum):
    """Target length/density of the projection."""
    
    SUMMARY = "summary"  # Brief overview
    STANDARD = "standard"  # Normal length
    COMPREHENSIVE = "comprehensive"  # Include everything


class MergeStrategy(str, Enum):
    """How to merge content from multiple contributors."""
    
    WEAVE = "weave"  # Seamlessly blend all perspectives into unified narrative
    SEPARATE_VOICES = "separate_voices"  # Keep distinct voice sections (e.g., "Sarah remembers...")
    SUBJECT_PRIMARY = "subject_primary"  # Subject's words are primary, others add context
    EQUAL_VOICES = "equal_voices"  # Give equal weight to all contributors
    ANNOTATED = "annotated"  # Main narrative with contributor annotations


class ProjectionConfig(BaseModel):
    """
    Configuration for how to generate a projection.
    
    This tells the ProjectionService how to transform
    the content pool into a document.
    """
    
    # Structure
    style: ProjectionStyle = ProjectionStyle.THEMATIC
    length: ProjectionLength = ProjectionLength.STANDARD
    
    # Update behavior
    default_update_mode: UpdateMode = UpdateMode.EVOLVE
    auto_update_on_content: bool = False  # Auto-update when content arrives?
    
    # Filtering
    contributor_filter: list[str] | None = None  # Only these contributors
    date_range: tuple[datetime, datetime] | None = None
    tag_filter: list[str] | None = None  # Content must have these tags
    exclude_tags: list[str] | None = None  # Exclude content with these
    
    # Section guidance (optional hints, not requirements)
    suggested_sections: list[str] | None = None  # ["childhood", "career"]
    min_sections: int = 1
    max_sections: int = 20
    
    # Tone/voice
    prompt_template: str | None = None  # Which prompt template to use
    voice_guidance: str | None = None  # "warm and nostalgic", "professional"
    
    # Behavior
    include_empty_sections: bool = False  # Show sections with no content?
    merge_similar: bool = True  # Combine similar content?
    
    # Multi-contributor merging
    merge_strategy: MergeStrategy = MergeStrategy.WEAVE
    show_attributions: bool = False  # Show who contributed each piece?
    subject_contributor_id: str | None = None  # The main subject's contributor ID
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style.value,
            "length": self.length.value,
            "default_update_mode": self.default_update_mode.value,
            "contributor_filter": self.contributor_filter,
            "tag_filter": self.tag_filter,
            "suggested_sections": self.suggested_sections,
            "min_sections": self.min_sections,
            "max_sections": self.max_sections,
            "voice_guidance": self.voice_guidance,
        }


# =============================================================================
# Document Projection Version
# =============================================================================


class ProjectionVersion(BaseModel):
    """A snapshot of a projection at a point in time."""
    
    version: int
    created_at: datetime = Field(default_factory=utc_now)
    
    # What triggered this version
    trigger: str = "generation"  # generation, update, manual
    update_mode: UpdateMode | None = None
    
    # Stats at this version
    section_count: int = 0
    word_count: int = 0
    content_item_count: int = 0
    
    # Brief description of changes
    change_summary: str = ""


# =============================================================================
# Document Projection
# =============================================================================


class DocumentProjection(BaseModel):
    """
    A projected view of the content pool.
    
    This is a COMPUTED document - it doesn't hold the source of truth,
    it's a transformation of the content pool based on configuration.
    
    Key behaviors:
    - Regenerate: Re-compute from content pool (respecting locked sections)
    - Evolve: Integrate new content while preserving structure
    - Lock section: Freeze a section so it won't change
    - Multiple projections: Same content can have multiple projections
      (e.g., "Full Book", "Gift Summary", "Print Version")
    
    Documents are versioned - each update creates a new version
    that can be compared or reverted.
    """
    
    id: str = Field(default_factory=lambda: generate_id("doc"))
    
    # What this projection belongs to
    project_id: str
    
    # Identity
    name: str  # "Full Memoir", "Birthday Summary", "Print Version"
    description: str = ""
    
    # The actual sections
    sections: list[ProjectedSection] = Field(default_factory=list)
    
    # How this projection was/should be generated
    config: ProjectionConfig = Field(default_factory=ProjectionConfig)
    
    # Narrative context - AI's understanding of the content
    context: NarrativeContext = Field(default_factory=NarrativeContext)
    
    # Versioning
    version: int = 1
    version_history: list[ProjectionVersion] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_regenerated: datetime | None = None
    
    # What content was included in last generation
    content_snapshot_ids: list[str] = Field(default_factory=list)
    
    # Multi-contributor tracking
    contributor_ids: list[str] = Field(default_factory=list)
    contributor_summary: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # contributor_summary: {"contrib_123": {"name": "Sarah", "role": "family", "sections": 3, "content_items": 5}}
    
    # Stats
    word_count: int = 0
    
    # ==========================================================================
    # Section Management
    # ==========================================================================
    
    def get_section(self, section_id: str) -> ProjectedSection | None:
        """Get a section by ID."""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None
    
    def get_section_by_title(self, title: str) -> ProjectedSection | None:
        """Get a section by title (case-insensitive)."""
        title_lower = title.lower()
        for section in self.sections:
            if section.title.lower() == title_lower:
                return section
        return None
    
    def add_section(self, section: ProjectedSection) -> None:
        """Add a section to the projection."""
        section.order = len(self.sections)
        self.sections.append(section)
        self._update_stats()
    
    def remove_section(self, section_id: str) -> bool:
        """Remove a section. Returns True if found and removed."""
        for i, section in enumerate(self.sections):
            if section.id == section_id:
                self.sections.pop(i)
                self._reorder_sections()
                self._update_stats()
                return True
        return False
    
    def reorder_sections(self, section_ids: list[str]) -> None:
        """Reorder sections based on provided ID order."""
        id_to_section = {s.id: s for s in self.sections}
        new_order = []
        for i, sid in enumerate(section_ids):
            if sid in id_to_section:
                section = id_to_section[sid]
                section.order = i
                new_order.append(section)
        self.sections = new_order
    
    def _reorder_sections(self) -> None:
        """Renumber section orders after changes."""
        for i, section in enumerate(self.sections):
            section.order = i
    
    # ==========================================================================
    # Lock Management
    # ==========================================================================
    
    def lock_section(self, section_id: str, user_id: str, reason: str = "approved") -> bool:
        """Lock a section. Returns True if found."""
        section = self.get_section(section_id)
        if section:
            section.lock(user_id, reason)
            return True
        return False
    
    def unlock_section(self, section_id: str) -> bool:
        """Unlock a section. Returns True if found."""
        section = self.get_section(section_id)
        if section:
            section.unlock()
            return True
        return False
    
    def get_locked_sections(self) -> list[ProjectedSection]:
        """Get all locked sections."""
        return [s for s in self.sections if s.is_locked]
    
    def get_regeneratable_sections(self) -> list[ProjectedSection]:
        """Get sections that can be regenerated."""
        return [s for s in self.sections if s.can_regenerate]
    
    def get_stale_sections(self, current_content_ids: list[str]) -> list[ProjectedSection]:
        """Get sections that are stale (have new content available)."""
        return [
            s for s in self.sections
            if s.can_regenerate and s.is_stale(current_content_ids)
        ]
    
    # ==========================================================================
    # Content & Stats
    # ==========================================================================
    
    def get_full_text(self) -> str:
        """Get the full document as text."""
        parts = []
        for section in sorted(self.sections, key=lambda s: s.order):
            if section.content:
                parts.append(f"## {section.title}\n\n{section.content}")
        return "\n\n".join(parts)
    
    def _update_stats(self) -> None:
        """Update word count and other stats."""
        self.word_count = sum(
            len(section.content.split())
            for section in self.sections
            if section.content
        )
        self.updated_at = utc_now()
    
    # ==========================================================================
    # Versioning
    # ==========================================================================
    
    def _save_version(
        self,
        trigger: str,
        update_mode: UpdateMode | None = None,
        change_summary: str = "",
    ) -> None:
        """Save current state as a version."""
        self.version_history.append(ProjectionVersion(
            version=self.version,
            trigger=trigger,
            update_mode=update_mode,
            section_count=len(self.sections),
            word_count=self.word_count,
            content_item_count=len(self.content_snapshot_ids),
            change_summary=change_summary,
        ))
        
        # Keep only last 20 versions
        if len(self.version_history) > 20:
            self.version_history = self.version_history[-20:]
    
    def mark_updated(
        self,
        content_ids: list[str],
        update_mode: UpdateMode,
        change_summary: str = "",
    ) -> None:
        """Mark that this projection was updated."""
        # Save version before incrementing
        self._save_version(
            trigger="update",
            update_mode=update_mode,
            change_summary=change_summary,
        )
        
        self.version += 1
        self.updated_at = utc_now()
        self.last_regenerated = utc_now()
        self.content_snapshot_ids = content_ids
        self._update_stats()
    
    def mark_regenerated(self, content_ids: list[str]) -> None:
        """Mark that this projection was fully regenerated (legacy compat)."""
        self.mark_updated(content_ids, UpdateMode.REGENERATE, "Full regeneration")
    
    # ==========================================================================
    # Status
    # ==========================================================================
    
    def get_status(self) -> dict[str, Any]:
        """Get a status summary of the projection."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "sections_count": len(self.sections),
            "locked_count": len(self.get_locked_sections()),
            "word_count": self.word_count,
            "last_updated": self.updated_at.isoformat() if self.updated_at else None,
            "last_regenerated": self.last_regenerated.isoformat() if self.last_regenerated else None,
            "content_items_used": len(self.content_snapshot_ids),
            "themes_count": len(self.context.themes),
        }
    
    def get_update_options(self, current_content_ids: list[str]) -> dict[str, Any]:
        """Get available update options based on current state."""
        stale_sections = self.get_stale_sections(current_content_ids)
        regeneratable = self.get_regeneratable_sections()
        locked = self.get_locked_sections()
        
        new_content_count = len(set(current_content_ids) - set(self.content_snapshot_ids))
        
        return {
            "has_new_content": new_content_count > 0,
            "new_content_count": new_content_count,
            "stale_section_count": len(stale_sections),
            "stale_section_ids": [s.id for s in stale_sections],
            "regeneratable_count": len(regeneratable),
            "locked_count": len(locked),
            "available_modes": [
                {
                    "mode": UpdateMode.EVOLVE.value,
                    "description": "Integrate new content while preserving existing structure",
                    "affects_sections": len(stale_sections),
                },
                {
                    "mode": UpdateMode.REGENERATE.value,
                    "description": "Fully regenerate unlocked sections from all content",
                    "affects_sections": len(regeneratable),
                },
                {
                    "mode": UpdateMode.REFRESH.value,
                    "description": "Only update sections with new relevant content",
                    "affects_sections": len(stale_sections),
                },
            ],
        }
    
    # ==========================================================================
    # Multi-Contributor Support
    # ==========================================================================
    
    def update_contributor_summary(
        self, 
        contributors: dict[str, dict[str, Any]]
    ) -> None:
        """
        Update the contributor summary for this projection.
        
        Args:
            contributors: Dict of contributor_id -> {name, role, relationship, ...}
        """
        self.contributor_ids = list(contributors.keys())
        
        # Build summary with contribution stats
        for contrib_id, info in contributors.items():
            sections_count = sum(
                1 for s in self.sections 
                if contrib_id in s.contributor_ids
            )
            content_count = sum(
                len([cid for cid in s.source_content_ids if cid])  # Simplified
                for s in self.sections 
                if contrib_id in s.contributor_ids
            )
            
            self.contributor_summary[contrib_id] = {
                "name": info.get("name", "Unknown"),
                "role": info.get("role", "family"),
                "relationship": info.get("relationship"),
                "sections_contributed": sections_count,
                "is_subject": info.get("role") == "subject",
            }
    
    def get_contributor_sections(self, contributor_id: str) -> list[ProjectedSection]:
        """Get all sections a contributor contributed to."""
        return [s for s in self.sections if contributor_id in s.contributor_ids]
    
    def get_contributions_by_contributor(self) -> dict[str, list[str]]:
        """Get a mapping of contributor_id -> list of section titles."""
        result: dict[str, list[str]] = {}
        for section in self.sections:
            for contrib_id in section.contributor_ids:
                if contrib_id not in result:
                    result[contrib_id] = []
                result[contrib_id].append(section.title)
        return result


# =============================================================================
# Content Pool (project-level content store)
# =============================================================================


class ContentPool(BaseModel):
    """
    All content for a project - the source of truth.
    
    This is separate from ContentItem storage in the executor.
    The ContentPool is the unified view that projections are built from.
    """
    
    project_id: str
    
    # All content item IDs in this pool
    content_ids: list[str] = Field(default_factory=list)
    
    # Cached metadata for quick filtering
    # (In production, this would query the content store)
    contributor_ids: set[str] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    
    # Stats
    total_items: int = 0
    last_updated: datetime = Field(default_factory=utc_now)
    
    def add_content(self, content_id: str, contributor_id: str, tags: list[str]) -> None:
        """Add content to the pool."""
        if content_id not in self.content_ids:
            self.content_ids.append(content_id)
            self.contributor_ids.add(contributor_id)
            self.tags.update(tags)
            self.total_items = len(self.content_ids)
            self.last_updated = utc_now()
    
    def get_new_content_ids(self, since_ids: list[str]) -> list[str]:
        """Get content IDs that are new since the given snapshot."""
        since_set = set(since_ids)
        return [cid for cid in self.content_ids if cid not in since_set]
    
    def get_filtered_ids(
        self,
        contributor_filter: list[str] | None = None,
        tag_filter: list[str] | None = None,
    ) -> list[str]:
        """
        Get content IDs matching filters.
        
        Note: In production, this would query the actual content store.
        Here we just return all IDs since we don't have the full content.
        """
        # Simplified - real implementation would filter properly
        return self.content_ids
