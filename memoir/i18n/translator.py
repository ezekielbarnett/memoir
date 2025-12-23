"""
LLM-powered translator with caching.

Uses the same LLM infrastructure as the rest of the system.
Caches translations by content hash for efficiency.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from functools import lru_cache

import dspy

from memoir.i18n.languages import Language, normalize_language_code, get_language_name


# =============================================================================
# DSPy Signatures for Translation
# =============================================================================


class TranslateText(dspy.Signature):
    """Translate text while preserving meaning, tone, and style."""
    
    text: str = dspy.InputField(desc="Text to translate")
    source_language: str = dspy.InputField(desc="Source language code (e.g., 'en')")
    target_language: str = dspy.InputField(desc="Target language code (e.g., 'es')")
    context: str = dspy.InputField(desc="Context about the text (optional)", default="")
    
    translated_text: str = dspy.OutputField(desc="Translated text")


class DetectLanguage(dspy.Signature):
    """Detect the language of text."""
    
    text: str = dspy.InputField(desc="Text to analyze")
    
    language_code: str = dspy.OutputField(desc="ISO 639-1 language code (e.g., 'en', 'es', 'fr')")
    confidence: float = dspy.OutputField(desc="Confidence score 0-1")


class TranslateBatch(dspy.Signature):
    """Translate multiple texts efficiently."""
    
    texts: list[str] = dspy.InputField(desc="List of texts to translate")
    source_language: str = dspy.InputField(desc="Source language code")
    target_language: str = dspy.InputField(desc="Target language code")
    context: str = dspy.InputField(desc="Shared context for all texts", default="")
    
    translated_texts: list[str] = dspy.OutputField(desc="List of translated texts in same order")


# =============================================================================
# Translation Cache
# =============================================================================


class TranslationCache:
    """
    Simple hash-based translation cache.
    
    In production, this would use Redis or similar.
    For now, uses in-memory dict with optional persistence.
    """
    
    def __init__(self, storage=None):
        self._cache: dict[str, str] = {}
        self._storage = storage  # Optional persistent storage
    
    def _make_key(self, text: str, source: str, target: str) -> str:
        """Create cache key from content hash."""
        content = f"{source}:{target}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def get(self, text: str, source: str, target: str) -> str | None:
        """Get cached translation."""
        key = self._make_key(text, source, target)
        
        # Check memory cache first
        if key in self._cache:
            return self._cache[key]
        
        # Check persistent storage
        if self._storage:
            cached = await self._storage.cache.get(f"trans:{key}")
            if cached:
                self._cache[key] = cached  # Populate memory cache
                return cached
        
        return None
    
    async def set(self, text: str, source: str, target: str, translation: str) -> None:
        """Cache a translation."""
        key = self._make_key(text, source, target)
        self._cache[key] = translation
        
        # Persist if storage available
        if self._storage:
            await self._storage.cache.set(
                f"trans:{key}",
                translation,
                ttl=60 * 60 * 24 * 30  # 30 days
            )
    
    def clear(self) -> None:
        """Clear memory cache."""
        self._cache.clear()


# =============================================================================
# Translator Service
# =============================================================================


class Translator:
    """
    Main translation service.
    
    Usage:
        translator = Translator()
        
        # Single translation
        es_text = await translator.translate("Hello", target="es")
        
        # With context (better quality)
        fr_text = await translator.translate(
            "She passed away in 2010",
            target="fr",
            context="life story memoir"
        )
        
        # Batch (more efficient)
        de_texts = await translator.translate_batch(
            ["Hello", "Goodbye", "Thank you"],
            target="de"
        )
        
        # Detect language
        lang = await translator.detect("Bonjour le monde")  # -> "fr"
    """
    
    def __init__(self, storage=None, default_source: str = "en"):
        self.cache = TranslationCache(storage)
        self.default_source = default_source
        
        # DSPy modules (lazy initialized)
        self._translate_module: dspy.Predict | None = None
        self._detect_module: dspy.Predict | None = None
        self._batch_module: dspy.Predict | None = None
    
    @property
    def translate_module(self) -> dspy.Predict:
        if self._translate_module is None:
            self._translate_module = dspy.Predict(TranslateText)
        return self._translate_module
    
    @property
    def detect_module(self) -> dspy.Predict:
        if self._detect_module is None:
            self._detect_module = dspy.Predict(DetectLanguage)
        return self._detect_module
    
    @property
    def batch_module(self) -> dspy.Predict:
        if self._batch_module is None:
            self._batch_module = dspy.Predict(TranslateBatch)
        return self._batch_module
    
    async def translate(
        self,
        text: str,
        target: str | Language,
        source: str | Language | None = None,
        context: str = "",
        use_cache: bool = True,
    ) -> str:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target: Target language code
            source: Source language (auto-detect if None)
            context: Optional context for better translation
            use_cache: Whether to use cache
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # Normalize language codes
        target = normalize_language_code(str(target))
        source = normalize_language_code(str(source)) if source else self.default_source
        
        # Same language? Return as-is
        if source == target:
            return text
        
        # Check cache
        if use_cache:
            cached = await self.cache.get(text, source, target)
            if cached:
                return cached
        
        # Translate via LLM
        try:
            from memoir.services.ai.client import configure_lm
            configure_lm()
            
            result = self.translate_module(
                text=text,
                source_language=get_language_name(source),
                target_language=get_language_name(target),
                context=context or "general text",
            )
            
            translation = result.translated_text.strip()
            
            # Cache result
            if use_cache:
                await self.cache.set(text, source, target, translation)
            
            return translation
            
        except Exception as e:
            # On error, return original text with warning
            print(f"⚠️ Translation failed: {e}")
            return text
    
    async def translate_batch(
        self,
        texts: list[str],
        target: str | Language,
        source: str | Language | None = None,
        context: str = "",
        use_cache: bool = True,
    ) -> list[str]:
        """
        Translate multiple texts efficiently.
        
        Uses batch API when possible, falls back to individual translations.
        """
        if not texts:
            return []
        
        target = normalize_language_code(str(target))
        source = normalize_language_code(str(source)) if source else self.default_source
        
        if source == target:
            return texts
        
        # Check cache for each text
        results: list[str | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        
        if use_cache:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results[i] = text
                    continue
                    
                cached = await self.cache.get(text, source, target)
                if cached:
                    results[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts
        
        # Translate uncached texts
        if uncached_texts:
            try:
                from memoir.services.ai.client import configure_lm
                configure_lm()
                
                # Try batch translation
                result = self.batch_module(
                    texts=uncached_texts,
                    source_language=get_language_name(source),
                    target_language=get_language_name(target),
                    context=context or "general text",
                )
                
                translations = result.translated_texts
                
                # Handle if LLM returns wrong number
                if len(translations) != len(uncached_texts):
                    # Fall back to individual translations
                    translations = [
                        await self.translate(t, target, source, context, use_cache=False)
                        for t in uncached_texts
                    ]
                
                # Fill in results and cache
                for i, (orig_idx, translation) in enumerate(zip(uncached_indices, translations)):
                    results[orig_idx] = translation.strip()
                    if use_cache:
                        await self.cache.set(
                            uncached_texts[i], source, target, translation.strip()
                        )
                        
            except Exception as e:
                print(f"⚠️ Batch translation failed: {e}")
                # Return original texts on error
                for i, orig_idx in enumerate(uncached_indices):
                    results[orig_idx] = uncached_texts[i]
        
        return [r if r is not None else texts[i] for i, r in enumerate(results)]
    
    async def detect(self, text: str) -> tuple[str, float]:
        """
        Detect language of text.
        
        Returns:
            Tuple of (language_code, confidence)
        """
        if not text or not text.strip():
            return "en", 0.0
        
        try:
            from memoir.services.ai.client import configure_lm
            configure_lm()
            
            result = self.detect_module(text=text[:500])  # Limit text length
            
            return (
                normalize_language_code(result.language_code),
                float(result.confidence)
            )
        except Exception as e:
            print(f"⚠️ Language detection failed: {e}")
            return "en", 0.0


# =============================================================================
# Module-level convenience functions
# =============================================================================


_translator: Translator | None = None


def get_translator(storage=None) -> Translator:
    """Get or create the global translator instance."""
    global _translator
    if _translator is None:
        _translator = Translator(storage)
    return _translator


async def translate(
    text: str,
    target: str | Language,
    source: str | Language | None = None,
    context: str = "",
) -> str:
    """Translate text (convenience function)."""
    return await get_translator().translate(text, target, source, context)


async def translate_batch(
    texts: list[str],
    target: str | Language,
    source: str | Language | None = None,
    context: str = "",
) -> list[str]:
    """Translate multiple texts (convenience function)."""
    return await get_translator().translate_batch(texts, target, source, context)


async def detect_language(text: str) -> tuple[str, float]:
    """Detect language (convenience function)."""
    return await get_translator().detect(text)

