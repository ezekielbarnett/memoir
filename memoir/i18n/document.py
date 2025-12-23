"""
Document-level translation helpers.

Translates entire projections, sections, or content items.
"""

from __future__ import annotations

from typing import Any

from memoir.i18n.translator import get_translator, Translator
from memoir.i18n.languages import Language


async def translate_projection(
    projection: dict[str, Any],
    target: str | Language,
    source: str | Language = "en",
    include_metadata: bool = False,
) -> dict[str, Any]:
    """
    Translate an entire document projection.
    
    Translates:
    - Document name and description
    - All section titles and content
    - Theme names and descriptions
    
    Args:
        projection: Projection dict (from API response)
        target: Target language
        source: Source language
        include_metadata: Also translate metadata fields
    
    Returns:
        Translated projection (new dict, original unchanged)
    """
    translator = get_translator()
    
    # Copy to avoid mutating original
    result = projection.copy()
    
    # Translate name and description
    if result.get("name"):
        result["name"] = await translator.translate(
            result["name"], target, source,
            context="document title for a life story memoir"
        )
    
    if result.get("description"):
        result["description"] = await translator.translate(
            result["description"], target, source,
            context="document description"
        )
    
    # Translate sections
    if "sections" in result:
        result["sections"] = await translate_sections(
            result["sections"], target, source
        )
    
    # Translate narrative context themes
    if "context" in result and result["context"].get("themes"):
        result["context"] = result["context"].copy()
        result["context"]["themes"] = [
            {
                **theme,
                "theme": await translator.translate(
                    theme.get("theme", ""), target, source,
                    context="theme name for life story"
                ),
                "description": await translator.translate(
                    theme.get("description", ""), target, source,
                    context="theme description"
                ),
            }
            for theme in result["context"]["themes"]
        ]
    
    # Mark as translated
    result["_translated"] = {
        "target_language": str(target),
        "source_language": str(source),
    }
    
    return result


async def translate_sections(
    sections: list[dict[str, Any]],
    target: str | Language,
    source: str | Language = "en",
) -> list[dict[str, Any]]:
    """
    Translate a list of sections.
    
    Uses batch translation for efficiency where possible.
    """
    translator = get_translator()
    
    # Collect all texts to translate
    titles = [s.get("title", "") for s in sections]
    contents = [s.get("content", "") for s in sections]
    summaries = [s.get("summary", "") for s in sections]
    
    # Batch translate
    translated_titles = await translator.translate_batch(
        titles, target, source,
        context="section titles for life story memoir"
    )
    
    translated_contents = await translator.translate_batch(
        contents, target, source,
        context="narrative content from a life story memoir, preserve emotional tone"
    )
    
    translated_summaries = await translator.translate_batch(
        summaries, target, source,
        context="section summaries"
    )
    
    # Build translated sections
    result = []
    for i, section in enumerate(sections):
        translated_section = section.copy()
        translated_section["title"] = translated_titles[i]
        translated_section["content"] = translated_contents[i]
        if summaries[i]:
            translated_section["summary"] = translated_summaries[i]
        result.append(translated_section)
    
    return result


async def translate_content_item(
    content: dict[str, Any],
    target: str | Language,
    source: str | Language = "en",
) -> dict[str, Any]:
    """
    Translate a content item (user's original contribution).
    
    Translates question and answer text.
    """
    translator = get_translator()
    result = content.copy()
    
    inner = result.get("content", {})
    if isinstance(inner, dict):
        inner = inner.copy()
        
        # Translate question
        if inner.get("question_text"):
            inner["question_text"] = await translator.translate(
                inner["question_text"], target, source,
                context="interview question for life story"
            )
        if inner.get("question"):
            inner["question"] = await translator.translate(
                inner["question"], target, source,
                context="interview question for life story"
            )
        
        # Translate answer
        if inner.get("answer_text"):
            inner["answer_text"] = await translator.translate(
                inner["answer_text"], target, source,
                context="personal story/memory from an elderly person"
            )
        
        result["content"] = inner
    
    return result


async def translate_questions(
    questions: list[dict[str, Any]],
    target: str | Language,
    source: str | Language = "en",
) -> list[dict[str, Any]]:
    """
    Translate a list of questions (from question bank).
    
    Useful for translating the question prompts shown to users.
    """
    translator = get_translator()
    
    # Collect texts
    question_texts = [q.get("question", q.get("text", "")) for q in questions]
    
    # Batch translate
    translated = await translator.translate_batch(
        question_texts, target, source,
        context="interview questions for recording life stories"
    )
    
    # Build result
    result = []
    for i, q in enumerate(questions):
        translated_q = q.copy()
        if "question" in translated_q:
            translated_q["question"] = translated[i]
        if "text" in translated_q:
            translated_q["text"] = translated[i]
        result.append(translated_q)
    
    return result

