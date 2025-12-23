"""
Question bank resource.

Question banks are collections of questions that can be asked
during content collection. They support categorization, follow-ups,
and variable interpolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoir.resources.base import Resource


@dataclass
class Question:
    """A single question in a question bank."""
    
    id: str
    text: str
    
    # Categorization
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    
    # Follow-up questions (asked after this one is answered)
    follow_ups: list[str] = field(default_factory=list)
    
    # Conditions for when to ask this question
    # e.g., {"requires_tags": ["childhood"]} - only ask if childhood tag present
    conditions: dict[str, Any] = field(default_factory=dict)
    
    # Priority (higher = more likely to be selected)
    priority: int = 1
    
    # Whether this question can be skipped
    skippable: bool = True
    
    def interpolate(self, context: dict[str, Any]) -> str:
        """
        Interpolate variables in the question text.
        
        Supports {subject.name}, {contributor.name}, etc.
        """
        text = self.text
        
        # Handle nested keys like {subject.name}
        for key, value in context.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    text = text.replace(f"{{{key}.{subkey}}}", str(subvalue))
            else:
                text = text.replace(f"{{{key}}}", str(value))
        
        return text
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "text": self.text,
        }
        
        if self.tags:
            result["tags"] = self.tags
        if self.category:
            result["category"] = self.category
        if self.follow_ups:
            result["follow_ups"] = self.follow_ups
        if self.conditions:
            result["conditions"] = self.conditions
        if self.priority != 1:
            result["priority"] = self.priority
        if not self.skippable:
            result["skippable"] = self.skippable
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Question:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            text=data["text"],
            tags=data.get("tags", []),
            category=data.get("category"),
            follow_ups=data.get("follow_ups", []),
            conditions=data.get("conditions", {}),
            priority=data.get("priority", 1),
            skippable=data.get("skippable", True),
        )


class QuestionBank(Resource):
    """
    A collection of questions for content collection.
    
    Question banks can be referenced by product definitions and
    used with different selection strategies.
    """
    
    def __init__(
        self,
        resource_id: str,
        questions: list[Question],
        name: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        version: int = 1,
    ):
        self._resource_id = resource_id
        self._questions = questions
        self._name = name or resource_id.replace("_", " ").title()
        self._description = description
        self._tags = tags or []
        self._version = version
        
        # Build lookup indexes
        self._by_id: dict[str, Question] = {q.id: q for q in questions}
        self._by_tag: dict[str, list[Question]] = {}
        self._by_category: dict[str, list[Question]] = {}
        
        for q in questions:
            for tag in q.tags:
                if tag not in self._by_tag:
                    self._by_tag[tag] = []
                self._by_tag[tag].append(q)
            
            if q.category:
                if q.category not in self._by_category:
                    self._by_category[q.category] = []
                self._by_category[q.category].append(q)
    
    @property
    def resource_id(self) -> str:
        return self._resource_id
    
    @property
    def resource_type(self) -> str:
        return "questions"
    
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
    def questions(self) -> list[Question]:
        """All questions in the bank."""
        return self._questions
    
    def get_question(self, question_id: str) -> Question | None:
        """Get a question by ID."""
        return self._by_id.get(question_id)
    
    def get_by_tag(self, tag: str) -> list[Question]:
        """Get all questions with a specific tag."""
        return self._by_tag.get(tag, [])
    
    def get_by_category(self, category: str) -> list[Question]:
        """Get all questions in a category."""
        return self._by_category.get(category, [])
    
    def get_unanswered(
        self,
        answered_ids: set[str],
        context: dict[str, Any] | None = None,
    ) -> list[Question]:
        """
        Get questions that haven't been answered yet.
        
        Optionally filters by conditions based on context.
        """
        unanswered = [q for q in self._questions if q.id not in answered_ids]
        
        if context:
            # Filter by conditions
            filtered = []
            for q in unanswered:
                if self._matches_conditions(q, context):
                    filtered.append(q)
            unanswered = filtered
        
        return unanswered
    
    def _matches_conditions(self, question: Question, context: dict[str, Any]) -> bool:
        """Check if a question's conditions are met."""
        conditions = question.conditions
        
        if not conditions:
            return True
        
        # Check required tags
        if "requires_tags" in conditions:
            context_tags = set(context.get("tags", []))
            required = set(conditions["requires_tags"])
            if not required.issubset(context_tags):
                return False
        
        # Check excluded tags
        if "excludes_tags" in conditions:
            context_tags = set(context.get("tags", []))
            excluded = set(conditions["excludes_tags"])
            if context_tags.intersection(excluded):
                return False
        
        return True
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self._resource_id,
            "name": self._name,
            "description": self._description,
            "version": self._version,
            "tags": self._tags,
            "questions": [q.to_dict() for q in self._questions],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestionBank:
        """Create from dictionary."""
        questions = [Question.from_dict(q) for q in data.get("questions", [])]
        
        return cls(
            resource_id=data["id"],
            questions=questions,
            name=data.get("name"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            version=data.get("version", 1),
        )

