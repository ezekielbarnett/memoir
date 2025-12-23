"""
Memoir Platform - Main entry point.

This module demonstrates how to use the memoir platform
and can be run to verify the installation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from memoir.core.registry import get_registry, reset_registry
from memoir.core.events import get_event_bus, reset_event_bus
from memoir.config_loader import load_config
from memoir.products.executor import ProductExecutor


async def demo():
    """
    Run a demonstration of the memoir platform.
    
    This creates a project, adds a contributor, and shows
    how content flows through the system.
    """
    print("=" * 60)
    print("MEMOIR PLATFORM DEMO")
    print("=" * 60)
    print()
    
    # Reset singletons for clean demo
    reset_registry()
    reset_event_bus()
    
    # Load configuration
    print("Loading configuration...")
    counts = load_config()
    print(f"  ✓ Loaded {counts['questions']} question banks")
    print(f"  ✓ Loaded {counts['prompts']} prompt templates")
    print(f"  ✓ Loaded {counts['templates']} document templates")
    print(f"  ✓ Loaded {counts['products']} product definitions")
    print()
    
    # Show available products
    registry = get_registry()
    print("Available products:")
    for product_id in registry.list_products():
        config = registry.get_product(product_id)
        print(f"  • {product_id}: {config.get('name', 'Unnamed')}")
    print()
    
    # Show available question banks
    print("Available question banks:")
    for bank_id in registry.list_resources("questions"):
        bank = registry.get_resource("questions", bank_id)
        print(f"  • {bank_id}: {len(bank.questions)} questions")
    print()
    
    # Create an executor
    executor = ProductExecutor()
    
    # Create a demo project
    print("Creating demo project...")
    project = await executor.create_project(
        product_id="birthday_tribute",
        name="Sarah's 40th Birthday Book",
        owner_id="user_demo",
        subject_name="Sarah Johnson",
        subject_data={"birth_date": "1985-03-15"},
    )
    print(f"  ✓ Created project: {project.id}")
    print(f"  ✓ Status: {project.status.value}")
    print()
    
    # List contributors
    contributors = executor.list_contributors(project.id)
    print(f"Contributors ({len(contributors)}):")
    for c in contributors:
        print(f"  • {c.name} ({c.relationship}) - {c.status.value}")
    print()
    
    # Add another contributor
    print("Adding contributor...")
    friend = await executor.add_contributor(
        project_id=project.id,
        name="Mike Chen",
        email="mike@example.com",
        relationship="friend",
    )
    print(f"  ✓ Added: {friend.name}")
    print(f"  ✓ Invite token: {friend.invite_token}")
    print()
    
    # Start collection
    print("Starting collection phase...")
    project = await executor.start_collection(project.id)
    print(f"  ✓ Status: {project.status.value}")
    print()
    
    # Simulate adding content
    print("Adding sample content...")
    content = await executor.add_content(
        project_id=project.id,
        contributor_id=friend.id,
        content_type="structured_qa",
        content={
            "question_id": "first_memory",
            "question_text": "What's your earliest memory of Sarah?",
            "answer_text": "I remember meeting Sarah at a coffee shop in 2010. "
                          "She was reading a book about astronomy and we started "
                          "talking about the stars. That conversation lasted three "
                          "hours and we've been friends ever since.",
        },
        source_interface="web_form",
        question_id="first_memory",
        tags=["friendship", "meeting", "first_impression"],
    )
    print(f"  ✓ Added content: {content.id}")
    print()
    
    # Show event history
    event_bus = get_event_bus()
    events = event_bus.get_history(project_id=project.id)
    print(f"Event history ({len(events)} events):")
    for event in events[-5:]:  # Show last 5
        print(f"  • {event.event_type}")
    print()
    
    print("=" * 60)
    print("Demo complete!")
    print()
    print("Next steps:")
    print("  1. Register services (transcription, ai_writer, etc.)")
    print("  2. Register interfaces (voice_recorder, pdf_export, etc.)")
    print("  3. Wire services to event bus: executor.wire_services()")
    print("  4. Build a web API on top of the executor")
    print("=" * 60)


def main():
    """Main entry point."""
    asyncio.run(demo())


if __name__ == "__main__":
    main()

