"""
Document template resource.

Document templates define the structure of the final output.
They specify sections, how content maps to sections, and
formatting rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from memoir.resources.base import Resource


class SectionSource(str, Enum):
    """How a section gets its content."""
    
    AI_GENERATED = "ai_generated"  # AI generates content for this section
    DIRECT_CONTENT = "direct_content"  # Content items are included directly
    DIRECT_QUOTES = "direct_quotes"  # Pull quotes from content
    METADATA = "metadata"  # Project/subject metadata
    CUSTOM = "custom"  # Custom logic


@dataclass
class Section:
    """A section in the document template."""
    
    id: str
    name: str
    
    # How this section gets content
    source: SectionSource = SectionSource.AI_GENERATED
    
    # For AI_GENERATED: which prompt to use
    prompt_ref: str | None = None
    
    # For DIRECT_CONTENT/DIRECT_QUOTES: filter for content
    content_filter: dict[str, Any] = field(default_factory=dict)
    
    # For METADATA: which fields to include
    metadata_fields: list[str] = field(default_factory=list)
    
    # Display options
    optional: bool = False
    order: int = 0
    
    # Nested sections
    subsections: list[Section] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "source": self.source.value,
        }
        
        if self.prompt_ref:
            result["prompt_ref"] = self.prompt_ref
        if self.content_filter:
            result["content_filter"] = self.content_filter
        if self.metadata_fields:
            result["metadata_fields"] = self.metadata_fields
        if self.optional:
            result["optional"] = self.optional
        if self.order:
            result["order"] = self.order
        if self.subsections:
            result["subsections"] = [s.to_dict() for s in self.subsections]
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Section:
        subsections = [cls.from_dict(s) for s in data.get("subsections", [])]
        
        return cls(
            id=data["id"],
            name=data["name"],
            source=SectionSource(data.get("source", "ai_generated")),
            prompt_ref=data.get("prompt_ref"),
            content_filter=data.get("content_filter", {}),
            metadata_fields=data.get("metadata_fields", []),
            optional=data.get("optional", False),
            order=data.get("order", 0),
            subsections=subsections,
        )


class DocumentTemplate(Resource):
    """
    A template for the final document structure.
    
    Document templates define what sections appear in the output,
    how they're ordered, and where their content comes from.
    """
    
    def __init__(
        self,
        resource_id: str,
        sections: list[Section],
        name: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        version: int = 1,
        styles: dict[str, Any] | None = None,
    ):
        self._resource_id = resource_id
        self._sections = sections
        self._name = name or resource_id.replace("_", " ").title()
        self._description = description
        self._tags = tags or []
        self._version = version
        self._styles = styles or {}
        
        # Build section lookup
        self._by_id: dict[str, Section] = {}
        self._build_index(sections)
    
    def _build_index(self, sections: list[Section]) -> None:
        """Build section lookup index recursively."""
        for section in sections:
            self._by_id[section.id] = section
            self._build_index(section.subsections)
    
    @property
    def resource_id(self) -> str:
        return self._resource_id
    
    @property
    def resource_type(self) -> str:
        return "templates"
    
    @property
    def version(self) -> int:
        return self._version
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def tags(self) -> list[str]:
        return self._tags
    
    @property
    def sections(self) -> list[Section]:
        """Top-level sections in order."""
        return sorted(self._sections, key=lambda s: s.order)
    
    @property
    def styles(self) -> dict[str, Any]:
        """Style configuration for rendering."""
        return self._styles
    
    def get_section(self, section_id: str) -> Section | None:
        """Get a section by ID."""
        return self._by_id.get(section_id)
    
    def get_required_sections(self) -> list[Section]:
        """Get all non-optional sections."""
        return [s for s in self._sections if not s.optional]
    
    def get_ai_generated_sections(self) -> list[Section]:
        """Get sections that need AI generation."""
        return [s for s in self._by_id.values() if s.source == SectionSource.AI_GENERATED]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self._resource_id,
            "name": self._name,
            "description": self._description,
            "version": self._version,
            "tags": self._tags,
            "styles": self._styles,
            "sections": [s.to_dict() for s in self._sections],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentTemplate:
        sections = [Section.from_dict(s) for s in data.get("sections", [])]
        
        return cls(
            resource_id=data["id"],
            sections=sections,
            name=data.get("name"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            version=data.get("version", 1),
            styles=data.get("styles"),
        )

