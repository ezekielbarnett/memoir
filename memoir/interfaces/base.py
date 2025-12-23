"""
Base classes for input and output interfaces.

Interfaces are the adapters that connect the outside world to the
event-driven core. Input interfaces receive raw content and emit events.
Output interfaces take processed content and produce deliverables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from memoir.core.events import Event
from memoir.core.models import ContentItem


@dataclass
class InputContext:
    """Context provided to input interfaces when receiving content."""
    
    project_id: str
    contributor_id: str
    
    # Optional context
    question_id: str | None = None
    question_text: str | None = None
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class InputInterface(ABC):
    """
    Base class for input interfaces.
    
    Input interfaces receive raw content (audio, text, images, etc.)
    and convert it into standardized content items and events.
    
    Example:
        class VoiceRecorderInterface(InputInterface):
            interface_id = "voice_recorder"
            
            async def receive(self, raw_input, context):
                # raw_input is audio blob
                text = await self.transcription_service.transcribe(raw_input)
                
                content_item = ContentItem(
                    project_id=context.project_id,
                    contributor_id=context.contributor_id,
                    content_type=ContentType.STRUCTURED_QA,
                    content={
                        "question_id": context.question_id,
                        "question_text": context.question_text,
                        "answer_text": text,
                    },
                    source_interface=self.interface_id,
                )
                
                return [
                    content_created(...),
                    question_answered(...),
                ]
    """
    
    @property
    @abstractmethod
    def interface_id(self) -> str:
        """Unique identifier for this interface."""
        pass
    
    @property
    def display_name(self) -> str:
        """Human-readable name for this interface."""
        return self.interface_id.replace("_", " ").title()
    
    @property
    def description(self) -> str:
        """Description of what this interface does."""
        return ""
    
    @property
    def supported_input_types(self) -> list[str]:
        """
        MIME types or input type identifiers this interface accepts.
        
        e.g., ["audio/webm", "audio/wav"] for voice recorder
        """
        return []
    
    @abstractmethod
    async def receive(
        self,
        raw_input: Any,
        context: InputContext,
    ) -> list[Event]:
        """
        Receive raw input and produce events.
        
        Args:
            raw_input: The raw content (audio blob, form data, etc.)
            context: Information about the project and contributor
            
        Returns:
            List of events (typically content.created plus any follow-ups)
        """
        pass
    
    async def validate(self, raw_input: Any) -> tuple[bool, str | None]:
        """
        Validate raw input before processing.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the interface with configuration."""
        pass
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass


@dataclass
class ExportResult:
    """Result of an export operation."""
    
    success: bool
    
    # For successful exports
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    
    # For failed exports
    error: str | None = None
    
    # Metadata
    export_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(
        cls,
        url: str,
        filename: str,
        mime_type: str,
        size_bytes: int | None = None,
        **metadata,
    ) -> ExportResult:
        """Create a successful export result."""
        return cls(
            success=True,
            url=url,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            metadata=metadata,
        )
    
    @classmethod
    def failure_result(cls, error: str, **metadata) -> ExportResult:
        """Create a failed export result."""
        return cls(
            success=False,
            error=error,
            metadata=metadata,
        )


@dataclass
class ExportConfig:
    """Configuration for an export operation."""
    
    project_id: str
    
    # What to export
    include_raw_content: bool = False
    include_processed_content: bool = True
    include_metadata: bool = True
    
    # Format-specific options
    options: dict[str, Any] = field(default_factory=dict)


class OutputInterface(ABC):
    """
    Base class for output interfaces.
    
    Output interfaces take processed content and produce deliverables
    in various formats (PDF, web viewer, book, etc.).
    
    Example:
        class PDFExportInterface(OutputInterface):
            interface_id = "pdf_export"
            
            async def export(self, content_items, config):
                pdf_bytes = self.render_pdf(content_items, config)
                url = await self.storage.upload(pdf_bytes, "memoir.pdf")
                
                return ExportResult.success_result(
                    url=url,
                    filename="memoir.pdf",
                    mime_type="application/pdf",
                    size_bytes=len(pdf_bytes),
                )
    """
    
    @property
    @abstractmethod
    def interface_id(self) -> str:
        """Unique identifier for this interface."""
        pass
    
    @property
    def display_name(self) -> str:
        """Human-readable name for this interface."""
        return self.interface_id.replace("_", " ").title()
    
    @property
    def description(self) -> str:
        """Description of what this interface produces."""
        return ""
    
    @property
    def output_mime_type(self) -> str:
        """MIME type of the output this interface produces."""
        return "application/octet-stream"
    
    @abstractmethod
    async def export(
        self,
        content_items: list[ContentItem],
        config: ExportConfig,
    ) -> ExportResult:
        """
        Export content items to the target format.
        
        Args:
            content_items: The content to export
            config: Export configuration
            
        Returns:
            Result of the export operation
        """
        pass
    
    async def preview(
        self,
        content_items: list[ContentItem],
        config: ExportConfig,
    ) -> str:
        """
        Generate a preview (if supported).
        
        Returns:
            URL or data URI for the preview
        """
        raise NotImplementedError("This interface does not support preview")
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the interface with configuration."""
        pass
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass

