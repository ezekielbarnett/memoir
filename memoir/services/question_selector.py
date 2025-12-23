"""
Question Selector Service.

Selects the next question to ask a contributor based on
various strategies: sequential, random, AI-adaptive, etc.

Supports phased products by filtering questions to the current phase.
"""

from __future__ import annotations

import random
from typing import Any

from memoir.core.events import Event
from memoir.core.models import Contributor, PhaseStatus
from memoir.core.registry import get_registry
from memoir.services.base import Service
from memoir.resources.question_bank import QuestionBank, Question
from memoir.products.loader import ProductDefinition, PhaseConfig


class QuestionSelectorService(Service):
    """
    Service that selects the next question to ask.
    
    Supports multiple strategies:
    - sequential: Go through questions in order
    - random: Pick randomly from remaining questions
    - ai_adaptive: Use AI to pick based on previous answers
    - ai_generative: Generate new questions based on context
    
    For phased products, questions are filtered to only those
    matching the contributor's current phase.
    """
    
    @property
    def service_id(self) -> str:
        return "question_selector"
    
    @property
    def subscribes_to(self) -> list[str]:
        return ["question.requested"]
    
    def __init__(self):
        self.registry = get_registry()
        # Track answered questions per contributor
        self._answered: dict[str, set[str]] = {}  # contributor_id -> set of question_ids
        # Contributor cache (in production, would be from DB)
        self._contributors: dict[str, Contributor] = {}
    
    def register_contributor(self, contributor: Contributor) -> None:
        """Register a contributor for phase-aware selection."""
        self._contributors[contributor.id] = contributor
    
    async def handle(self, event: Event) -> list[Event]:
        """Handle a question.requested event."""
        project_id = event.project_id
        contributor_id = event.contributor_id
        
        if not contributor_id:
            return []
        
        # Get project configuration
        try:
            product_config = self.registry.get_product(
                self._get_product_id(project_id)
            )
            product = ProductDefinition.from_dict(product_config)
        except Exception:
            # Fall back to defaults if product not found
            product_config = {}
            product = None
        
        # Get question bank
        resources = product_config.get("resources", {})
        bank_id = resources.get("questions", "birthday_memories")
        
        try:
            bank = self.registry.get_resource("questions", bank_id)
        except Exception:
            # No question bank available
            return [self._no_questions_event(event)]
        
        # Get context for interpolation
        context = event.payload.get("context", {})
        
        # Track answered questions
        key = f"{project_id}:{contributor_id}"
        if key not in self._answered:
            self._answered[key] = set()
        answered = self._answered[key]
        
        # Get contributor for phase info
        contributor = self._contributors.get(contributor_id)
        
        # Determine which questions are available (phase filtering)
        available_questions = self._get_available_questions(
            bank, product, contributor, answered
        )
        
        if not available_questions:
            # Check if this is phase complete or truly exhausted
            if contributor and product and product.is_phased:
                return [self._phase_questions_complete_event(event, contributor)]
            return [self._no_questions_event(event)]
        
        # Get question selection config (phase-specific or global)
        selection_config = self._get_selection_config(product, contributor)
        strategy = selection_config.get("strategy", "sequential")
        
        # Select question based on strategy
        if strategy == "sequential":
            question = self._select_sequential_from_list(available_questions)
        elif strategy == "random":
            question = self._select_random_from_list(available_questions)
        elif strategy == "ai_adaptive":
            question = await self._select_ai_adaptive(
                available_questions, answered, context, selection_config
            )
        elif strategy == "ai_generative":
            question = await self._generate_question(context, selection_config)
        else:
            question = self._select_sequential_from_list(available_questions)
        
        if question is None:
            return [self._no_questions_event(event)]
        
        # Build response payload
        payload = {
            "question_id": question.id,
            "question_text": question.interpolate(context),
            "question_tags": question.tags,
            "strategy": strategy,
        }
        
        # Add phase info if applicable
        if contributor and contributor.current_phase_id:
            payload["phase_id"] = contributor.current_phase_id
            progress = contributor.get_current_phase()
            if progress:
                payload["phase_progress"] = {
                    "answered": progress.questions_answered,
                    "total": progress.questions_total,
                }
        
        # Return question.selected event
        return [Event(
            event_type="question.selected",
            project_id=project_id,
            contributor_id=contributor_id,
            payload=payload,
            correlation_id=event.correlation_id or event.id,
            causation_id=event.id,
        )]
    
    def _get_available_questions(
        self,
        bank: QuestionBank,
        product: ProductDefinition | None,
        contributor: Contributor | None,
        answered: set[str],
    ) -> list[Question]:
        """
        Get questions available for the contributor.
        
        For phased products, filters to current phase.
        For non-phased products, returns all unanswered.
        """
        # Start with all unanswered questions
        all_questions = bank.get_unanswered(answered)
        
        # If not phased or no contributor, return all
        if not product or not product.is_phased or not contributor:
            return all_questions
        
        # Get current phase
        current_phase_id = contributor.current_phase_id
        if not current_phase_id:
            return []  # No active phase
        
        phase = product.get_phase(current_phase_id)
        if not phase:
            return all_questions  # Phase not found, return all
        
        # Filter questions by phase criteria
        return self._filter_questions_for_phase(all_questions, phase)
    
    def _filter_questions_for_phase(
        self,
        questions: list[Question],
        phase: PhaseConfig,
    ) -> list[Question]:
        """Filter questions to those matching the phase criteria."""
        filters = phase.questions_filter
        
        # If explicit question IDs, use those
        if filters.question_ids:
            return [q for q in questions if q.id in filters.question_ids]
        
        filtered = questions
        
        # Filter by categories
        if filters.categories:
            filtered = [
                q for q in filtered
                if q.category and q.category in filters.categories
            ]
        
        # Filter by tags (question must have at least one matching tag)
        if filters.tags:
            filtered = [
                q for q in filtered
                if any(tag in filters.tags for tag in q.tags)
            ]
        
        # Apply limits
        if filters.max_questions:
            filtered = filtered[:filters.max_questions]
        
        return filtered
    
    def _get_selection_config(
        self,
        product: ProductDefinition | None,
        contributor: Contributor | None,
    ) -> dict[str, Any]:
        """Get question selection config, preferring phase-specific if available."""
        if product and product.is_phased and contributor and contributor.current_phase_id:
            phase = product.get_phase(contributor.current_phase_id)
            if phase:
                return {
                    "strategy": phase.question_selection.strategy,
                    "min_questions": phase.question_selection.min_questions,
                    "max_questions": phase.question_selection.max_questions,
                    "ai_config": phase.question_selection.ai_config,
                }
        
        # Fall back to global collection config
        if product:
            return {
                "strategy": product.collection.question_selection.strategy,
                "min_questions": product.collection.question_selection.min_questions,
                "max_questions": product.collection.question_selection.max_questions,
                "ai_config": product.collection.question_selection.ai_config,
            }
        
        return {"strategy": "sequential"}
    
    def _select_sequential_from_list(self, questions: list[Question]) -> Question | None:
        """Select the first question from the list."""
        return questions[0] if questions else None
    
    def _select_random_from_list(self, questions: list[Question]) -> Question | None:
        """Select a random question from the list."""
        return random.choice(questions) if questions else None
    
    def _get_product_id(self, project_id: str) -> str:
        """Get the product ID for a project."""
        # In a real implementation, this would look up the project
        # For now, return a default
        return "birthday_tribute"
    
    async def _select_ai_adaptive(
        self,
        questions: list[Question],
        answered: set[str],
        context: dict[str, Any],
        config: dict[str, Any],
    ) -> Question | None:
        """
        Use AI to select the most relevant next question.
        
        This is a placeholder - real implementation would call an LLM
        to analyze previous answers and pick the best follow-up.
        """
        if not questions:
            return None
        
        # Weight by priority
        weights = [q.priority for q in questions]
        return random.choices(questions, weights=weights, k=1)[0]
    
    async def _generate_question(
        self,
        context: dict[str, Any],
        config: dict[str, Any],
    ) -> Question | None:
        """
        Generate a new question using AI.
        
        This is a placeholder - real implementation would call an LLM
        to generate contextually relevant questions.
        """
        # Placeholder: return a generic follow-up question
        return Question(
            id="generated_followup",
            text="Can you tell me more about that?",
            tags=["follow_up", "generated"],
        )
    
    def _no_questions_event(self, original: Event) -> Event:
        """Create an event indicating no more questions."""
        return Event(
            event_type="question.exhausted",
            project_id=original.project_id,
            contributor_id=original.contributor_id,
            payload={"message": "All questions have been answered"},
            correlation_id=original.correlation_id or original.id,
            causation_id=original.id,
        )
    
    def _phase_questions_complete_event(
        self,
        original: Event,
        contributor: Contributor,
    ) -> Event:
        """Create an event indicating current phase questions are complete."""
        return Event(
            event_type="phase.questions_complete",
            project_id=original.project_id,
            contributor_id=original.contributor_id,
            payload={
                "phase_id": contributor.current_phase_id,
                "message": "All questions in this phase have been answered",
            },
            correlation_id=original.correlation_id or original.id,
            causation_id=original.id,
        )
    
    def mark_answered(
        self,
        project_id: str,
        contributor_id: str,
        question_id: str,
    ) -> None:
        """Mark a question as answered for a contributor."""
        key = f"{project_id}:{contributor_id}"
        if key not in self._answered:
            self._answered[key] = set()
        self._answered[key].add(question_id)
        
        # Update phase progress if contributor has phases
        contributor = self._contributors.get(contributor_id)
        if contributor:
            progress = contributor.get_current_phase()
            if progress and progress.status == PhaseStatus.IN_PROGRESS:
                progress.record_answer()
    
    def reset_contributor(self, project_id: str, contributor_id: str) -> None:
        """Reset answered questions for a contributor."""
        key = f"{project_id}:{contributor_id}"
        self._answered.pop(key, None)
    
    def get_phase_progress(
        self,
        contributor_id: str,
    ) -> dict[str, Any] | None:
        """Get phase progress for a contributor."""
        contributor = self._contributors.get(contributor_id)
        if not contributor or not contributor.current_phase_id:
            return None
        
        progress = contributor.get_current_phase()
        if not progress:
            return None
        
        return {
            "phase_id": contributor.current_phase_id,
            "status": progress.status.value,
            "questions_answered": progress.questions_answered,
            "questions_total": progress.questions_total,
        }

