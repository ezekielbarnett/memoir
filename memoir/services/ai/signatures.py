"""
DSPy Signatures for memoir generation.

Signatures define the input/output structure for AI tasks.
DSPy handles prompting, parsing, and can optimize these over time.
"""

from __future__ import annotations

import dspy


# =============================================================================
# Section Generation
# =============================================================================


class GenerateSection(dspy.Signature):
    """
    Generate a memoir section from collected content.
    
    Takes raw content (transcribed voice, form answers) and transforms
    it into polished, engaging prose for a specific section of the memoir.
    """
    
    section_title: str = dspy.InputField(desc="Title of the section to generate")
    raw_content: str = dspy.InputField(desc="Raw content from voice recordings and forms")
    style_guidance: str = dspy.InputField(desc="Writing style guidance (e.g., 'warm and nostalgic')")
    narrative_context: str = dspy.InputField(desc="Summary of the story so far, key themes, facts")
    target_length: str = dspy.InputField(desc="Target length: 'brief', 'standard', 'detailed'")
    
    section_content: str = dspy.OutputField(desc="The generated section prose")
    section_summary: str = dspy.OutputField(desc="One-sentence summary of this section")


class RegenerateSection(dspy.Signature):
    """
    Regenerate a section incorporating new content.
    
    Used when new content arrives and we need to update a section
    while maintaining narrative continuity.
    """
    
    section_title: str = dspy.InputField(desc="Title of the section")
    existing_content: str = dspy.InputField(desc="Current section content")
    new_raw_content: str = dspy.InputField(desc="New raw content to incorporate")
    style_guidance: str = dspy.InputField(desc="Writing style guidance")
    
    updated_content: str = dspy.OutputField(desc="Updated section with new content woven in")


# =============================================================================
# Theme Extraction
# =============================================================================


class ExtractThemes(dspy.Signature):
    """
    Extract themes and key information from content.
    
    Analyzes collected content to identify recurring themes, important
    facts, and narrative threads that should inform future sections.
    """
    
    content: str = dspy.InputField(desc="Raw content to analyze")
    existing_themes: str = dspy.InputField(desc="Already identified themes (JSON list)")
    
    themes: str = dspy.OutputField(desc="JSON list of themes with strength scores")
    key_facts: str = dspy.OutputField(desc="JSON dict of important facts extracted")
    suggested_topics: str = dspy.OutputField(desc="JSON list of topics to explore further")
    emotional_tone: str = dspy.OutputField(desc="Overall emotional tone of the content")


# =============================================================================
# Question Selection
# =============================================================================


class SelectQuestions(dspy.Signature):
    """
    Select and potentially generate follow-up questions.
    
    Based on what's been collected so far, choose the best next
    questions to ask or generate new ones to fill gaps.
    """
    
    available_questions: str = dspy.InputField(desc="JSON list of available questions")
    answered_topics: str = dspy.InputField(desc="Topics already covered")
    narrative_context: str = dspy.InputField(desc="Story context and themes so far")
    target_count: int = dspy.InputField(desc="Number of questions to select")
    
    selected_questions: str = dspy.OutputField(desc="JSON list of selected question IDs")
    generated_questions: str = dspy.OutputField(desc="JSON list of new questions to ask")
    reasoning: str = dspy.OutputField(desc="Brief explanation of selection logic")


# =============================================================================
# Summarization
# =============================================================================


class SummarizeContent(dspy.Signature):
    """
    Create a summary of content for context building.
    """
    
    content: str = dspy.InputField(desc="Content to summarize")
    max_length: int = dspy.InputField(desc="Maximum summary length in words")
    
    summary: str = dspy.OutputField(desc="Concise summary")


class SummarizeStory(dspy.Signature):
    """
    Create a narrative summary of the entire story so far.
    
    Used to build context for AI when generating new sections
    or selecting questions.
    """
    
    sections: str = dspy.InputField(desc="JSON list of section titles and summaries")
    themes: str = dspy.InputField(desc="Identified themes")
    
    narrative_summary: str = dspy.OutputField(desc="Flowing narrative summary of the story")
    voice_notes: str = dspy.OutputField(desc="Notes on the subject's voice and style")


# =============================================================================
# Document Structure
# =============================================================================


class SuggestSections(dspy.Signature):
    """
    Suggest section structure for a memoir based on content.
    
    Analyzes available content and suggests how to organize
    it into coherent sections.
    """
    
    content_summary: str = dspy.InputField(desc="Summary of all collected content")
    style: str = dspy.InputField(desc="Organization style: 'chronological', 'thematic', etc.")
    
    sections: str = dspy.OutputField(desc="JSON list of suggested sections with titles and descriptions")
    reasoning: str = dspy.OutputField(desc="Explanation of the suggested structure")

