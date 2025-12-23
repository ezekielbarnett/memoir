"""
Demo of phased product functionality with draft updates.

Shows how the monthly life story product works with:
- Phase unlocks and checkpoints
- Living document that updates after each phase
- Theme analysis for context-aware interactions
- Notifications
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from memoir.core.registry import get_registry, reset_registry
from memoir.core.events import get_event_bus, reset_event_bus, Event
from memoir.core.models import PhaseStatus, ContentItem, ContentType
from memoir.config_loader import load_config
from memoir.products.executor import ProductExecutor
from memoir.products.loader import ProductDefinition
from memoir.services.phase_manager import PhaseManager
from memoir.services.question_selector import QuestionSelectorService
from memoir.services.notification import NotificationService
from memoir.services.draft_updater import DraftUpdaterService
from memoir.services.theme_analyzer import ThemeAnalyzerService


async def demo_phased_product():
    """
    Demonstrate the phased product functionality with draft updates.
    """
    print("=" * 70)
    print("PHASED PRODUCT DEMO: Monthly Life Story with Living Document")
    print("=" * 70)
    print()
    
    # Reset singletons
    reset_registry()
    reset_event_bus()
    
    # Load configuration
    print("Loading configuration...")
    counts = load_config()
    print(f"  ✓ Loaded {counts['products']} products")
    print()
    
    # Get the phased product
    registry = get_registry()
    product_config = registry.get_product("monthly_life_story")
    product = ProductDefinition.from_dict(product_config)
    
    print(f"Product: {product.name}")
    print(f"Phased: {product.is_phased} ({len(product.phases)} phases)")
    print()
    
    # Show first phase's on_complete hooks
    first_phase = product.get_first_phase()
    if first_phase:
        print(f"First phase: {first_phase.name}")
        print(f"  on_complete hooks: {len(first_phase.on_complete)} services")
        for hook in first_phase.on_complete:
            print(f"    • {hook.service}")
    print()
    
    # Create services
    event_bus = get_event_bus()
    phase_manager = PhaseManager()
    question_selector = QuestionSelectorService()
    notification_service = NotificationService()
    draft_updater = DraftUpdaterService()
    theme_analyzer = ThemeAnalyzerService()
    
    # Connect theme analyzer to draft updater's draft store
    theme_analyzer.set_drafts_store(draft_updater._drafts)
    
    # Register services
    registry.register_service(phase_manager)
    registry.register_service(question_selector)
    registry.register_service(notification_service)
    registry.register_service(draft_updater)
    registry.register_service(theme_analyzer)
    
    # Wire to event bus
    for service in [phase_manager, notification_service, draft_updater, theme_analyzer]:
        for pattern in service.subscribes_to:
            event_bus.subscribe(pattern, service.handle)
    
    # Create executor and project
    executor = ProductExecutor(registry, event_bus)
    
    print("=" * 70)
    print("SIMULATING USER JOURNEY WITH DRAFT UPDATES")
    print("=" * 70)
    print()
    
    # Create project
    print("1. Creating project...")
    project = await executor.create_project(
        product_id="monthly_life_story",
        name="John's Life Story",
        owner_id="user_john",
        subject_name="John Smith",
        subject_data={"birth_year": 1960},
    )
    print(f"   ✓ Project: {project.id}")
    
    # Get contributor
    contributors = executor.list_contributors(project.id)
    contributor = contributors[0]
    print(f"   ✓ Contributor: {contributor.id}")
    print()
    
    # Initialize phases
    print("2. Initializing phases...")
    unlocked = phase_manager.initialize_contributor(contributor, product)
    question_selector.register_contributor(contributor)
    print(f"   ✓ Unlocked: {unlocked}")
    print()
    
    # Start first phase
    print("3. Starting first phase (Early Years)...")
    phase_manager.start_phase(contributor, "early_years")
    progress = contributor.get_current_phase()
    progress.questions_total = 4
    print(f"   ✓ Status: {progress.status.value}")
    print()
    
    # Simulate answering questions with actual content
    print("4. Answering questions (simulated)...")
    
    sample_answers = [
        {
            "question": "What's your earliest memory?",
            "answer": "I remember sitting on the back porch of our farmhouse in rural Ohio, watching fireflies dance in the summer twilight. I must have been about four years old. My grandmother was shelling peas beside me, and the rhythmic sound of pods popping open is still vivid in my mind. The air smelled of honeysuckle and fresh-cut grass."
        },
        {
            "question": "Describe your childhood home",
            "answer": "We lived in a white clapboard farmhouse that had been in my family for three generations. The kitchen was the heart of the home - there was always something cooking on the old cast-iron stove. I shared a room with my brother Tommy, and we'd spend hours looking out the window at the stars, making up stories about distant planets."
        },
        {
            "question": "What was your relationship with your parents like?",
            "answer": "My father was a quiet man who showed his love through actions rather than words. Every Sunday, he'd take me fishing at Miller's Pond. My mother was the opposite - warm, effusive, always singing while she worked. She taught me to read before I started school, sitting together in the rocking chair with worn copies of fairy tales."
        },
        {
            "question": "Did you have siblings?",
            "answer": "Tommy and I were inseparable. Being only two years apart, we were partners in crime - building forts, catching frogs, getting into trouble together. We also had a baby sister, Sarah, who came along when I was seven. She became the princess of our little kingdom, and we were her devoted protectors."
        },
    ]
    
    # Create content items
    content_items = []
    for i, qa in enumerate(sample_answers):
        content = ContentItem(
            project_id=project.id,
            contributor_id=contributor.id,
            content_type=ContentType.STRUCTURED_QA,
            content={
                "question_id": f"q_{i}",
                "question_text": qa["question"],
                "answer_text": qa["answer"],
            },
            source_interface="voice_recorder",
            tags=["childhood", "family"],
        )
        content_items.append(content)
        
        # Track the answer
        question_selector.mark_answered(project.id, contributor.id, f"q_{i}")
        print(f"   Answered: {qa['question'][:40]}...")
    
    # Store content for services
    draft_updater._content[project.id] = content_items
    theme_analyzer.set_content_store(project.id, content_items)
    
    print(f"\n   ✓ Phase progress: {progress.questions_answered}/{progress.questions_total}")
    print(f"   ✓ Phase status: {progress.status.value}")
    print()
    
    # Trigger phase completion
    print("5. Phase completes → Running on_complete hooks...")
    
    # Emit phase completed event
    phase_complete_event = Event(
        event_type="phase.completed",
        project_id=project.id,
        contributor_id=contributor.id,
        payload={
            "phase_id": "early_years",
            "phase_name": "The Early Years",
        },
    )
    
    results = await event_bus.publish(phase_complete_event)
    print(f"   ✓ Events emitted: {len(results)}")
    for event in results:
        print(f"     • {event.event_type}")
    print()
    
    # Show the draft
    print("6. Document Draft (Living Document):")
    print("-" * 50)
    draft = draft_updater.get_draft(contributor.id)
    if draft:
        print(f"   Title: {draft.title or '(Untitled - will be set on completion)'}")
        print(f"   Chapters: {len(draft.chapters)}")
        print(f"   Word count: {draft.word_count}")
        print(f"   Phases included: {draft.phases_included}")
        print()
        
        # Show chapter preview
        if draft.chapters:
            chapter = draft.chapters[0]
            print(f"   Chapter 1: {chapter.title}")
            print(f"   Preview:")
            preview = chapter.content[:300] + "..." if len(chapter.content) > 300 else chapter.content
            for line in preview.split('\n'):
                print(f"     {line}")
    print()
    
    # Show discovered themes
    print("7. Discovered Themes (AI Context):")
    print("-" * 50)
    if draft:
        context = draft.narrative_context
        print(f"   Summary: {context.summary}")
        print(f"   Themes: {len(context.themes)}")
        for theme in context.themes:
            print(f"     • {theme.theme} (strength: {theme.strength:.1f})")
        print(f"   Key facts: {context.key_facts}")
        print(f"   Suggested topics: {context.suggested_topics[:3]}")
    print()
    
    # Show notifications
    print("8. Notifications sent:")
    print("-" * 50)
    for notif in notification_service.get_sent_log():
        print(f"   [{notif['channel']}] {notif['template']}")
    print()
    
    print("=" * 70)
    print("HOW THIS WORKS")
    print("=" * 70)
    print("""
After completing "The Early Years" phase:

1. DRAFT UPDATER runs:
   - Collects all Q&A from the phase
   - Generates a chapter draft using AI
   - Adds chapter to the living document
   - User can see their story taking shape!

2. THEME ANALYZER runs:
   - Extracts themes: "family bonds", "nature and outdoors", "nostalgia"
   - Identifies key facts: mentioned places, years, people
   - Generates narrative summary
   - Suggests topics for future phases

3. NOTIFICATION SERVICE runs:
   - Sends "Chapter 1 is ready!" email
   - Includes link to preview the draft
   - User stays engaged between monthly sessions

4. CONTEXT FOR NEXT PHASE:
   - When "School Days" unlocks in 30 days
   - Question selector has context: "John grew up in rural Ohio..."
   - AI can ask more relevant follow-up questions
   - Writing will be more cohesive with earlier chapters
""")
    
    print("=" * 70)
    print("CONFIGURATION (from monthly_life_story.yaml)")
    print("=" * 70)
    print("""
phases:
  - id: early_years
    name: "The Early Years"
    # ... questions, unlock config ...
    
    on_complete:                          # ← NEW!
      - service: draft_updater            # Generate chapter
        config:
          mode: generate_chapter
          prompt_ref: literary_memoir.memoir
          
      - service: theme_analyzer           # Extract themes
        config:
          update_context: true
          extract_facts: true
          
      - service: notification             # Email user
        config:
          template: phase_complete_with_preview
          include_draft_link: true
""")


def main():
    """Main entry point."""
    asyncio.run(demo_phased_product())


if __name__ == "__main__":
    main()
