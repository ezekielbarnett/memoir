"""
AI services using DSPy with Gemini models.

DSPy provides a structured way to define AI behaviors as "signatures"
that can be optimized and tested.
"""

from memoir.services.ai.client import get_lm, configure_lm
from memoir.services.ai.signatures import (
    GenerateSection,
    ExtractThemes,
    SelectQuestions,
    SummarizeContent,
)
from memoir.services.ai.memoir import MemoirAI

__all__ = [
    "get_lm",
    "configure_lm",
    "GenerateSection",
    "ExtractThemes",
    "SelectQuestions",
    "SummarizeContent",
    "MemoirAI",
]

