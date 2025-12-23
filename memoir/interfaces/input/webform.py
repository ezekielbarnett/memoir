"""
Web Form Interface - Text-based content input.

Handles structured form submissions with questions and text answers.
"""

from __future__ import annotations

from typing import Any
import uuid

from memoir.core.events import Event
from memoir.core.models import ContentItem, ContentType
from memoir.interfaces.base import InputInterface, InputContext
from memoir.storage.base import StorageProvider


class WebFormInterface(InputInterface):
    """
    Interface for web form submissions.
    
    Handles:
    - Text answers to questions
    - Bio/profile data collection
    - Batch submissions
    """
    
    _interface_id = "web_form"
    
    @property
    def interface_id(self) -> str:
        return self._interface_id
    
    def __init__(self, storage: StorageProvider | None = None):
        self.storage = storage
    
    async def receive(
        self,
        raw_input: Any,
        context: InputContext,
    ) -> list[Event]:
        """
        Receive form input and produce events.
        
        Args:
            raw_input: Dict with 'question' and 'answer' (or list for batch)
            context: Input context with project/contributor info
            
        Returns:
            List of events (content.created for each answer)
        """
        events = []
        
        # Handle batch or single input
        if isinstance(raw_input, list):
            items = await self.process_batch(
                project_id=context.project_id,
                contributor_id=context.contributor_id,
                qa_pairs=raw_input,
                **context.metadata,
            )
        else:
            # Single Q&A
            question = raw_input.get("question", context.question_text or "")
            answer = raw_input.get("answer", raw_input.get("text", ""))
            
            item = await self.process(
                project_id=context.project_id,
                contributor_id=context.contributor_id,
                question=question,
                answer=answer,
                question_id=context.question_id,
                **context.metadata,
            )
            items = [item]
        
        # Create events for each content item
        for item in items:
            events.append(
                Event(
                    event_type="content.created",
                    project_id=context.project_id,
                    payload={
                        "content_item": item.model_dump(),
                        "source_interface": self.interface_id,
                    },
                    contributor_id=context.contributor_id,
                )
            )
        
        return events
    
    async def process(
        self,
        project_id: str,
        contributor_id: str,
        question: str,
        answer: str,
        question_id: str | None = None,
        **metadata: Any,
    ) -> ContentItem:
        """
        Process a single form answer.
        
        Args:
            project_id: Project this belongs to
            contributor_id: Who submitted this
            question: The question text
            answer: The answer text
            question_id: ID of the question (optional)
            **metadata: Additional metadata
        
        Returns:
            ContentItem with the answer
        """
        content_id = f"content_{uuid.uuid4().hex[:12]}"
        
        content_item = ContentItem(
            id=content_id,
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface=self.interface_id,
            content={
                "question": question,
                "question_id": question_id,
                "answer_text": answer,
            },
            source_metadata=metadata,
            tags=self._extract_tags(question),
        )
        
        # Store in metadata storage if available
        if self.storage:
            await self.storage.metadata.save(
                "content_items",
                content_id,
                content_item.model_dump(),
            )
        
        return content_item
    
    async def process_batch(
        self,
        project_id: str,
        contributor_id: str,
        qa_pairs: list[dict[str, str]],
        **metadata: Any,
    ) -> list[ContentItem]:
        """
        Process multiple Q&A pairs at once.
        
        Args:
            project_id: Project this belongs to
            contributor_id: Who submitted this
            qa_pairs: List of {"question": ..., "answer": ...} dicts
            **metadata: Additional metadata
        
        Returns:
            List of ContentItems
        """
        items = []
        for pair in qa_pairs:
            item = await self.process(
                project_id=project_id,
                contributor_id=contributor_id,
                question=pair.get("question", pair.get("q", "")),
                answer=pair.get("answer", pair.get("text", "")),
                question_id=pair.get("question_id"),
                **metadata,
            )
            items.append(item)
        return items
    
    async def process_bio(
        self,
        project_id: str,
        contributor_id: str,
        bio_data: dict[str, Any],
    ) -> ContentItem:
        """
        Process bio/profile data.
        
        Args:
            project_id: Project this belongs to
            contributor_id: Who this bio is for
            bio_data: Dict with fields like name, birth_year, etc.
        
        Returns:
            ContentItem with bio data
        """
        content_id = f"content_{uuid.uuid4().hex[:12]}"
        
        content_item = ContentItem(
            id=content_id,
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface=self.interface_id,
            content={
                "type": "bio",
                "bio_data": bio_data,
                "answer_text": self._bio_to_text(bio_data),
            },
            source_metadata={"form_type": "bio"},
            tags=["bio", "profile"],
        )
        
        if self.storage:
            await self.storage.metadata.save(
                "content_items",
                content_id,
                content_item.model_dump(),
            )
        
        return content_item
    
    def _bio_to_text(self, bio_data: dict[str, Any]) -> str:
        """Convert bio data to readable text."""
        parts = []
        if bio_data.get("name"):
            parts.append(f"Name: {bio_data['name']}")
        if bio_data.get("birth_year"):
            parts.append(f"Birth year: {bio_data['birth_year']}")
        if bio_data.get("birthplace"):
            parts.append(f"Birthplace: {bio_data['birthplace']}")
        # Add other fields
        for key, value in bio_data.items():
            if key not in ("name", "birth_year", "birthplace") and value:
                parts.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(parts)
    
    def _extract_tags(self, question: str | None) -> list[str]:
        """Extract simple tags from question text."""
        if not question:
            return []
        
        question_lower = question.lower()
        tags = []
        
        tag_keywords = {
            "childhood": ["childhood", "child", "young", "kid", "grew up"],
            "family": ["family", "parent", "mother", "father", "sibling", "brother", "sister"],
            "education": ["school", "teacher", "learn", "class", "education"],
            "home": ["home", "house", "room", "neighborhood"],
            "friends": ["friend", "friendship", "play"],
            "memory": ["memory", "remember", "recall", "first"],
            "career": ["work", "job", "career", "profession"],
            "relationships": ["relationship", "love", "partner", "married"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in question_lower for kw in keywords):
                tags.append(tag)
        
        return tags

