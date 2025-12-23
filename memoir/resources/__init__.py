"""Resources - versioned, editable data that services consume."""

from memoir.resources.base import Resource
from memoir.resources.question_bank import QuestionBank, Question
from memoir.resources.prompt_template import PromptTemplate
from memoir.resources.document_template import DocumentTemplate

__all__ = [
    "Resource",
    "QuestionBank",
    "Question",
    "PromptTemplate",
    "DocumentTemplate",
]

