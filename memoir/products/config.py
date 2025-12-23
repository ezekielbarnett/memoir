"""
Product configuration dataclasses.

These dataclasses represent the parsed configuration from YAML product definitions.
They define how content is collected, processed, and output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# Question Selection
# =============================================================================


@dataclass
class QuestionSelectionConfig:
    """Configuration for question selection within a phase or product."""
    
    strategy: str = "sequential"  # sequential, random, ai_adaptive, ai_generative
    min_questions: int = 1
    max_questions: int = 10
    
    # For ai_adaptive/ai_generative
    ai_config: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestionSelectionConfig:
        return cls(
            strategy=data.get("strategy", "sequential"),
            min_questions=data.get("min_questions", 1),
            max_questions=data.get("max_questions", 10),
            ai_config=data.get("ai_config", {}),
        )


# =============================================================================
# Contributor Settings
# =============================================================================


@dataclass
class ContributorConfig:
    """Configuration for contributor permissions and requirements."""
    
    allow_anonymous: bool = True
    max_contributors: int = 100
    require_relationship: bool = False
    require_email: bool = False
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContributorConfig:
        return cls(
            allow_anonymous=data.get("allow_anonymous", True),
            max_contributors=data.get("max_contributors", 100),
            require_relationship=data.get("require_relationship", False),
            require_email=data.get("require_email", False),
        )


# =============================================================================
# Collection Configuration
# =============================================================================


@dataclass
class CollectionConfig:
    """Configuration for content collection."""
    
    interfaces: list[str] = field(default_factory=list)
    question_selection: QuestionSelectionConfig = field(
        default_factory=QuestionSelectionConfig
    )
    contributor_settings: ContributorConfig = field(default_factory=ContributorConfig)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollectionConfig:
        return cls(
            interfaces=data.get("interfaces", []),
            question_selection=QuestionSelectionConfig.from_dict(
                data.get("question_selection", {})
            ),
            contributor_settings=ContributorConfig.from_dict(
                data.get("contributor_settings", {})
            ),
        )


# =============================================================================
# Phase Configuration
# =============================================================================


@dataclass
class PhaseUnlockConfig:
    """Configuration for how a phase unlocks."""
    
    unlock_type: str = "immediate"  # immediate, scheduled, on_completion, manual
    delay_days: int | None = None
    requires_phase: str | None = None
    delay_after_phase: bool = True
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> PhaseUnlockConfig:
        if isinstance(data, str):
            return cls(unlock_type=data)
        
        return cls(
            unlock_type=data.get("type", "immediate"),
            delay_days=data.get("delay_days"),
            requires_phase=data.get("requires"),
            delay_after_phase=data.get("delay_after_phase", True),
        )


@dataclass
class PhaseQuestionsFilter:
    """Filter for which questions belong to a phase."""
    
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)
    min_questions: int | None = None
    max_questions: int | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseQuestionsFilter:
        return cls(
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            question_ids=data.get("question_ids", []),
            min_questions=data.get("min_questions"),
            max_questions=data.get("max_questions"),
        )


@dataclass
class PhaseConfig:
    """Configuration for a single phase in the collection journey."""
    
    phase_id: str
    name: str
    description: str = ""
    questions_filter: PhaseQuestionsFilter = field(default_factory=PhaseQuestionsFilter)
    unlock: PhaseUnlockConfig = field(default_factory=PhaseUnlockConfig)
    question_selection: QuestionSelectionConfig = field(
        default_factory=QuestionSelectionConfig
    )
    order: int = 0
    required: bool = True
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseConfig:
        return cls(
            phase_id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            questions_filter=PhaseQuestionsFilter.from_dict(
                data.get("questions_filter", {})
            ),
            unlock=PhaseUnlockConfig.from_dict(data.get("unlock", "immediate")),
            question_selection=QuestionSelectionConfig.from_dict(
                data.get("question_selection", {})
            ),
            order=data.get("order", 0),
            required=data.get("required", True),
        )


# =============================================================================
# Projection Configuration (from YAML)
# =============================================================================


@dataclass
class ProjectionDefinition:
    """
    Defines a document projection available for the product.
    
    Content is primary, documents are projections. Each product can define
    one or more projection types that users can generate from their content.
    """
    
    projection_id: str
    name: str
    description: str = ""
    style: str = "thematic"  # chronological, thematic, by_contributor, freeform
    length: str = "standard"  # summary, standard, comprehensive
    suggested_sections: list[str] = field(default_factory=list)
    voice_guidance: str = ""
    prompt_template: str | None = None
    is_default: bool = False
    auto_update: bool = True  # Update when new content arrives?
    default_update_mode: str = "evolve"  # evolve, regenerate, refresh, append
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectionDefinition:
        return cls(
            projection_id=data.get("id", "default"),
            name=data.get("name", "Document"),
            description=data.get("description", ""),
            style=data.get("style", "thematic"),
            length=data.get("length", "standard"),
            suggested_sections=data.get("suggested_sections", []),
            voice_guidance=data.get("voice_guidance", ""),
            prompt_template=data.get("prompt_template"),
            is_default=data.get("is_default", False),
            auto_update=data.get("auto_update", True),
            default_update_mode=data.get("default_update_mode", "evolve"),
        )


@dataclass
class OutputConfig:
    """
    Configuration for document outputs (projections).
    
    Products define which projections are available and their defaults.
    """
    
    projections: list[ProjectionDefinition] = field(default_factory=list)
    allow_section_locking: bool = True
    allow_manual_edits: bool = True
    show_regenerate_option: bool = True
    show_update_options: bool = True
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputConfig:
        projections = [
            ProjectionDefinition.from_dict(p)
            for p in data.get("projections", [])
        ]
        
        # Default projection if none defined
        if not projections:
            projections = [ProjectionDefinition(
                projection_id="default",
                name="Full Document",
                style="thematic",
                is_default=True,
            )]
        
        return cls(
            projections=projections,
            allow_section_locking=data.get("allow_section_locking", True),
            allow_manual_edits=data.get("allow_manual_edits", True),
            show_regenerate_option=data.get("show_regenerate_option", True),
            show_update_options=data.get("show_update_options", True),
        )
    
    def get_default_projection(self) -> ProjectionDefinition | None:
        """Get the default projection definition."""
        for proj in self.projections:
            if proj.is_default:
                return proj
        return self.projections[0] if self.projections else None
    
    def get_projection(self, projection_id: str) -> ProjectionDefinition | None:
        """Get a projection definition by ID."""
        for proj in self.projections:
            if proj.projection_id == projection_id:
                return proj
        return None


# =============================================================================
# Notifications
# =============================================================================


@dataclass
class NotificationTrigger:
    """Configuration for a notification trigger."""
    
    event: str  # phase_unlock, phase_reminder, phase_complete, etc.
    channel: str = "email"  # email, sms, push
    template: str = ""
    delay_days: int | None = None
    only_if_not_started: bool = False
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationTrigger:
        return cls(
            event=data["event"],
            channel=data.get("channel", "email"),
            template=data.get("template", ""),
            delay_days=data.get("delay_days"),
            only_if_not_started=data.get("only_if_not_started", False),
        )


@dataclass
class NotificationsConfig:
    """Configuration for notifications."""
    
    enabled: bool = True
    triggers: list[NotificationTrigger] = field(default_factory=list)
    from_name: str | None = None
    reply_to: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationsConfig:
        triggers = [
            NotificationTrigger.from_dict(t)
            for t in data.get("triggers", [])
        ]
        return cls(
            enabled=data.get("enabled", True),
            triggers=triggers,
            from_name=data.get("from_name"),
            reply_to=data.get("reply_to"),
        )


# =============================================================================
# UI Configuration
# =============================================================================


@dataclass
class UIConfig:
    """Configuration for UI customization."""
    
    theme: str = "default"
    colors: dict[str, str] = field(default_factory=dict)
    logo_url: str | None = None
    custom_css: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UIConfig:
        return cls(
            theme=data.get("theme", "default"),
            colors=data.get("colors", {}),
            logo_url=data.get("logo_url"),
            custom_css=data.get("custom_css"),
        )


# =============================================================================
# Subject and Resources
# =============================================================================


@dataclass
class SubjectConfig:
    """Configuration for subject (who the memoir is about)."""
    
    required_fields: list[str] = field(default_factory=lambda: ["name"])
    optional_fields: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectConfig:
        return cls(
            required_fields=data.get("required_fields", ["name"]),
            optional_fields=data.get("optional_fields", []),
        )


@dataclass
class ResourceRefs:
    """References to resources used by the product."""
    
    questions: str | None = None
    prompts: str | None = None
    document_template: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceRefs:
        return cls(
            questions=data.get("questions"),
            prompts=data.get("prompts"),
            document_template=data.get("document_template"),
        )

