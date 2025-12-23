"""
MemoirAI - High-level AI service for memoir generation.

This wraps DSPy signatures into a clean interface for the rest
of the application to use.
"""

from __future__ import annotations

import json
from typing import Any

import dspy

from memoir.services.ai.signatures import (
    GenerateSection,
    RegenerateSection,
    ExtractThemes,
    SelectQuestions,
    SummarizeContent,
    SummarizeStory,
    SuggestSections,
)


class MemoirAI:
    """
    AI service for memoir generation tasks.
    
    Usage:
        from memoir.services.ai import MemoirAI, configure_lm
        
        configure_lm()  # Uses env vars
        ai = MemoirAI()
        
        section = ai.generate_section(
            title="Early Childhood",
            content="I grew up on a farm...",
            style="warm and nostalgic",
        )
    """
    
    def __init__(self):
        # DSPy modules (compiled signatures)
        self._generate_section = dspy.Predict(GenerateSection)
        self._regenerate_section = dspy.Predict(RegenerateSection)
        self._extract_themes = dspy.Predict(ExtractThemes)
        self._select_questions = dspy.Predict(SelectQuestions)
        self._summarize_content = dspy.Predict(SummarizeContent)
        self._summarize_story = dspy.Predict(SummarizeStory)
        self._suggest_sections = dspy.Predict(SuggestSections)
    
    # =========================================================================
    # Section Generation
    # =========================================================================
    
    def generate_section(
        self,
        title: str,
        content: str,
        style: str = "warm and engaging",
        context: str = "",
        length: str = "standard",
    ) -> dict[str, str]:
        """
        Generate a memoir section from raw content.
        
        Args:
            title: Section title
            content: Raw content (transcripts, form answers)
            style: Writing style guidance
            context: Narrative context from previous sections
            length: 'brief', 'standard', or 'detailed'
        
        Returns:
            Dict with 'content' and 'summary'
        """
        result = self._generate_section(
            section_title=title,
            raw_content=content,
            style_guidance=style,
            narrative_context=context or "This is the beginning of the memoir.",
            target_length=length,
        )
        
        return {
            "content": result.section_content,
            "summary": result.section_summary,
        }
    
    def regenerate_section(
        self,
        title: str,
        existing_content: str,
        new_content: str,
        style: str = "warm and engaging",
    ) -> str:
        """
        Update a section with new content while maintaining flow.
        """
        result = self._regenerate_section(
            section_title=title,
            existing_content=existing_content,
            new_raw_content=new_content,
            style_guidance=style,
        )
        
        return result.updated_content
    
    # =========================================================================
    # Theme Extraction
    # =========================================================================
    
    def extract_themes(
        self,
        content: str,
        existing_themes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Extract themes and key facts from content.
        
        Returns:
            Dict with 'themes', 'key_facts', 'suggested_topics', 'emotional_tone'
        """
        result = self._extract_themes(
            content=content,
            existing_themes=json.dumps(existing_themes or []),
        )
        
        return {
            "themes": self._safe_json_loads(result.themes, []),
            "key_facts": self._safe_json_loads(result.key_facts, {}),
            "suggested_topics": self._safe_json_loads(result.suggested_topics, []),
            "emotional_tone": result.emotional_tone,
        }
    
    # =========================================================================
    # Question Selection
    # =========================================================================
    
    def select_questions(
        self,
        available_questions: list[dict[str, Any]],
        answered_topics: list[str],
        context: str,
        count: int = 3,
    ) -> dict[str, Any]:
        """
        Select best questions to ask next.
        
        Returns:
            Dict with 'selected_ids', 'generated_questions', 'reasoning'
        """
        result = self._select_questions(
            available_questions=json.dumps(available_questions),
            answered_topics=", ".join(answered_topics) if answered_topics else "none",
            narrative_context=context,
            target_count=count,
        )
        
        return {
            "selected_ids": self._safe_json_loads(result.selected_questions, []),
            "generated_questions": self._safe_json_loads(result.generated_questions, []),
            "reasoning": result.reasoning,
        }
    
    # =========================================================================
    # Summarization
    # =========================================================================
    
    def summarize(self, content: str, max_words: int = 200) -> str:
        """Create a brief summary of content."""
        result = self._summarize_content(
            content=content,
            max_length=max_words,
        )
        return result.summary
    
    def summarize_story(
        self,
        sections: list[dict[str, str]],
        themes: list[str],
    ) -> dict[str, str]:
        """
        Create a narrative summary of the entire story.
        
        Returns:
            Dict with 'summary' and 'voice_notes'
        """
        result = self._summarize_story(
            sections=json.dumps(sections),
            themes=", ".join(themes),
        )
        
        return {
            "summary": result.narrative_summary,
            "voice_notes": result.voice_notes,
        }
    
    # =========================================================================
    # Document Structure
    # =========================================================================
    
    def suggest_sections(
        self,
        content_summary: str,
        style: str = "thematic",
    ) -> list[dict[str, str]]:
        """
        Suggest section structure for organizing content.
        
        Returns:
            List of dicts with 'title' and 'description'
        """
        result = self._suggest_sections(
            content_summary=content_summary,
            style=style,
        )
        
        return self._safe_json_loads(result.sections, [])
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    @staticmethod
    def _safe_json_loads(text: str, default: Any) -> Any:
        """Safely parse JSON, returning default on failure."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # Sometimes the LLM returns the JSON wrapped in markdown
            if "```" in text:
                # Extract JSON from markdown code block
                import re
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass
            return default

