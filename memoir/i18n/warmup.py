"""
Cache warming for translations.

Pre-translates static content (questions, UI strings, prompts) to priority
languages so users never hit a cold cache.

Run on:
- Application startup (optional, async)
- Deploy (recommended)
- Cron job (to catch new content)

Usage:
    # Warm all priority languages
    await warm_translation_cache()
    
    # Warm specific languages
    await warm_translation_cache(languages=["es", "fr", "de"])
    
    # CLI
    python -m memoir.i18n.warmup
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from memoir.i18n.translator import get_translator
from memoir.i18n.languages import (
    Language,
    WARM_UP_LANGUAGES,
    get_language_name,
)


# =============================================================================
# Content Loaders
# =============================================================================


def load_question_banks(config_dir: str = "config/questions") -> list[str]:
    """Load all questions from question bank YAML files."""
    questions: list[str] = []
    config_path = Path(config_dir)
    
    if not config_path.exists():
        print(f"⚠️  Question bank directory not found: {config_dir}")
        return questions
    
    for yaml_file in config_path.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            
            # Extract questions from various structures
            if isinstance(data, dict):
                # Handle question_bank format
                if "questions" in data:
                    for q in data["questions"]:
                        if isinstance(q, dict):
                            questions.append(q.get("question", q.get("text", "")))
                        elif isinstance(q, str):
                            questions.append(q)
                
                # Handle phases with questions
                if "phases" in data:
                    for phase in data["phases"]:
                        if isinstance(phase, dict) and "questions" in phase:
                            for q in phase["questions"]:
                                if isinstance(q, dict):
                                    questions.append(q.get("question", q.get("text", "")))
                                elif isinstance(q, str):
                                    questions.append(q)
            
            print(f"  ✓ Loaded {yaml_file.name}")
        except Exception as e:
            print(f"  ⚠️  Error loading {yaml_file}: {e}")
    
    # Filter empty
    questions = [q for q in questions if q and q.strip()]
    return questions


def load_prompt_templates(config_dir: str = "config/prompts") -> list[str]:
    """Load prompt templates that might be shown to users."""
    prompts: list[str] = []
    config_path = Path(config_dir)
    
    if not config_path.exists():
        return prompts
    
    for yaml_file in config_path.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            
            # Extract user-facing prompts
            if isinstance(data, dict):
                for key in ["description", "intro", "welcome", "instructions"]:
                    if key in data and data[key]:
                        prompts.append(data[key])
            
            print(f"  ✓ Loaded {yaml_file.name}")
        except Exception as e:
            print(f"  ⚠️  Error loading {yaml_file}: {e}")
    
    return prompts


# Common UI strings that should be pre-translated
UI_STRINGS = [
    # Navigation
    "Home",
    "Back",
    "Next",
    "Continue",
    "Skip",
    "Done",
    "Cancel",
    "Save",
    "Submit",
    
    # Recording
    "Start Recording",
    "Stop Recording",
    "Recording...",
    "Processing...",
    "Tap to record your answer",
    
    # Questions
    "Answer this question",
    "Tell us more",
    "Share your memories",
    "What else do you remember?",
    
    # Document
    "Your Life Story",
    "Chapter",
    "Section",
    "Table of Contents",
    "Introduction",
    "Conclusion",
    
    # Actions
    "Edit",
    "Delete",
    "Lock",
    "Unlock",
    "Download",
    "Share",
    "Print",
    "Export",
    "Translate",
    
    # Status
    "Saved",
    "Saving...",
    "Loading...",
    "Generating...",
    "Translating...",
    "Complete",
    "In Progress",
    "Not Started",
    
    # Errors
    "Something went wrong",
    "Please try again",
    "Connection lost",
    "Unable to save",
    
    # Encouragement
    "Great story!",
    "Thank you for sharing",
    "Your memories are precious",
    "Keep going!",
    
    # Section titles (commonly generated)
    "Early Years",
    "Childhood Memories",
    "Family",
    "Growing Up",
    "School Days",
    "First Love",
    "Career",
    "Marriage",
    "Parenthood",
    "Life Lessons",
    "Reflections",
    "Legacy",
]


# =============================================================================
# Cache Warming
# =============================================================================


async def warm_translation_cache(
    languages: list[str | Language] | None = None,
    include_questions: bool = True,
    include_prompts: bool = True,
    include_ui: bool = True,
    question_dir: str = "config/questions",
    prompt_dir: str = "config/prompts",
    batch_size: int = 20,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Pre-warm translation cache for priority languages.
    
    Args:
        languages: Languages to warm (defaults to WARM_UP_LANGUAGES)
        include_questions: Include question bank content
        include_prompts: Include prompt templates
        include_ui: Include common UI strings
        question_dir: Path to question YAML files
        prompt_dir: Path to prompt YAML files
        batch_size: Texts per batch (for LLM efficiency)
        verbose: Print progress
    
    Returns:
        Stats dict with counts
    """
    if languages is None:
        languages = WARM_UP_LANGUAGES
    
    # Normalize language codes
    lang_codes = [
        lang.value if isinstance(lang, Language) else str(lang)
        for lang in languages
    ]
    
    if verbose:
        print("=" * 60)
        print("🔥 TRANSLATION CACHE WARM-UP")
        print("=" * 60)
        print(f"\nTarget languages: {', '.join(lang_codes)}")
    
    # Collect all texts to translate
    all_texts: list[str] = []
    
    if include_questions:
        if verbose:
            print("\n📚 Loading question banks...")
        questions = load_question_banks(question_dir)
        all_texts.extend(questions)
        if verbose:
            print(f"   Found {len(questions)} questions")
    
    if include_prompts:
        if verbose:
            print("\n📝 Loading prompt templates...")
        prompts = load_prompt_templates(prompt_dir)
        all_texts.extend(prompts)
        if verbose:
            print(f"   Found {len(prompts)} prompts")
    
    if include_ui:
        all_texts.extend(UI_STRINGS)
        if verbose:
            print(f"\n🖥️  Added {len(UI_STRINGS)} UI strings")
    
    # Deduplicate
    all_texts = list(set(t for t in all_texts if t and t.strip()))
    
    if verbose:
        print(f"\n📊 Total unique texts: {len(all_texts)}")
        print(f"   × {len(lang_codes)} languages")
        print(f"   = {len(all_texts) * len(lang_codes)} translations needed")
    
    # Get translator
    translator = get_translator()
    
    # Warm each language
    stats = {
        "languages": len(lang_codes),
        "texts": len(all_texts),
        "translations": 0,
        "cached": 0,
        "errors": 0,
    }
    
    for lang in lang_codes:
        if verbose:
            print(f"\n🌍 Warming {get_language_name(lang)} ({lang})...")
        
        # Process in batches
        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i:i + batch_size]
            
            try:
                # Check what's already cached
                uncached = []
                for text in batch:
                    cached = await translator.cache.get(text, "en", lang)
                    if cached:
                        stats["cached"] += 1
                    else:
                        uncached.append(text)
                
                # Translate uncached
                if uncached:
                    await translator.translate_batch(
                        uncached,
                        target=lang,
                        source="en",
                        context="life story memoir application",
                    )
                    stats["translations"] += len(uncached)
                
                if verbose:
                    progress = min(i + batch_size, len(all_texts))
                    print(f"   {progress}/{len(all_texts)} texts", end="\r")
                    
            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    print(f"   ⚠️  Error in batch: {e}")
        
        if verbose:
            print(f"   ✓ {lang} complete")
    
    if verbose:
        print("\n" + "=" * 60)
        print("✅ WARM-UP COMPLETE")
        print("=" * 60)
        print(f"\n📊 Stats:")
        print(f"   Languages warmed: {stats['languages']}")
        print(f"   Unique texts: {stats['texts']}")
        print(f"   Already cached: {stats['cached']}")
        print(f"   New translations: {stats['translations']}")
        print(f"   Errors: {stats['errors']}")
    
    return stats


async def warm_single_language(
    language: str | Language,
    texts: list[str] | None = None,
    verbose: bool = True,
) -> int:
    """
    Warm cache for a single language.
    
    Useful when a new language is requested for the first time.
    
    Returns:
        Number of translations performed
    """
    lang = language.value if isinstance(language, Language) else language
    
    if texts is None:
        # Load default content
        texts = []
        texts.extend(load_question_banks())
        texts.extend(UI_STRINGS)
        texts = list(set(t for t in texts if t))
    
    if verbose:
        print(f"🔥 Warming {get_language_name(lang)}: {len(texts)} texts...")
    
    translator = get_translator()
    count = 0
    
    # Check what needs translating
    uncached = []
    for text in texts:
        cached = await translator.cache.get(text, "en", lang)
        if not cached:
            uncached.append(text)
    
    if uncached:
        await translator.translate_batch(
            uncached,
            target=lang,
            source="en",
            context="life story memoir application",
        )
        count = len(uncached)
    
    if verbose:
        print(f"   ✓ Translated {count} texts ({len(texts) - count} already cached)")
    
    return count


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """Run cache warm-up from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Warm translation cache for priority languages"
    )
    parser.add_argument(
        "--languages", "-l",
        nargs="+",
        help="Specific languages to warm (default: priority languages)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Warm ALL supported languages (slow!)"
    )
    parser.add_argument(
        "--questions-dir",
        default="config/questions",
        help="Path to question bank YAML files"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    
    args = parser.parse_args()
    
    if args.all:
        from memoir.i18n.languages import LTR_LANGUAGES
        languages = LTR_LANGUAGES
    else:
        languages = args.languages
    
    asyncio.run(warm_translation_cache(
        languages=languages,
        question_dir=args.questions_dir,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()

