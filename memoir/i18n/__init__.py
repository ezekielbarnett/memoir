"""
Internationalization - LLM-powered translation with caching.

Design:
1. Translate anything (UI strings, content, AI-generated prose)
2. Cache translations by content hash
3. Batch translate for efficiency
4. Lazy - only translates on request

Usage:
    from memoir.i18n import translate, Translator
    
    # Simple
    text_es = await translate("Hello world", target="es")
    
    # With context (better translations)
    text_fr = await translate(
        "She passed in 2010",
        target="fr", 
        context="life story about a grandmother"
    )
    
    # Batch
    texts_de = await translate_batch(["Hello", "Goodbye"], target="de")
"""

from memoir.i18n.translator import (
    Translator,
    get_translator,
    translate,
    translate_batch,
    detect_language,
)
from memoir.i18n.languages import (
    Language,
    SUPPORTED_LANGUAGES,
    WARM_UP_LANGUAGES,
    LTR_LANGUAGES,
    RTL_LANGUAGES,
    get_language_name,
    is_rtl,
)
from memoir.i18n.warmup import (
    warm_translation_cache,
    warm_single_language,
)
from memoir.i18n.document import (
    translate_projection,
    translate_sections,
    translate_content_item,
    translate_questions,
)

__all__ = [
    # Core translation
    "Translator",
    "get_translator",
    "translate",
    "translate_batch",
    "detect_language",
    # Document-level
    "translate_projection",
    "translate_sections",
    "translate_content_item",
    "translate_questions",
    # Cache warming
    "warm_translation_cache",
    "warm_single_language",
    # Language utilities
    "Language",
    "SUPPORTED_LANGUAGES",
    "WARM_UP_LANGUAGES",
    "LTR_LANGUAGES",
    "RTL_LANGUAGES",
    "get_language_name",
    "is_rtl",
]

