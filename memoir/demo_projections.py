"""
Demo: Content is Primary, Documents are Projections

This demonstrates the core philosophy:
- Content pool is the source of truth (all collected content)
- Documents are projections (computed views that can regenerate)
- Sections can be locked (preserve human edits / approved content)
- Multiple projections from same content (summary, full, by-contributor)

Run: python -m memoir.demo_projections
"""

import asyncio
from datetime import datetime, timezone

from memoir.core.models import ContentItem, Contributor, Project, ContentType
from memoir.core.projections import (
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    SectionState,
)
from memoir.services.projection import ProjectionService


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_projection(projection, show_content: bool = True):
    """Pretty print a projection."""
    print(f"\n📄 {projection.name}")
    print(f"   ID: {projection.id}")
    print(f"   Style: {projection.config.style.value}")
    print(f"   Words: {projection.word_count}")
    print(f"   Sections: {len(projection.sections)}")
    
    for section in projection.sections:
        state_emoji = {
            SectionState.GENERATED: "🔄",
            SectionState.LOCKED: "🔒",
            SectionState.DRAFT: "✏️",
            SectionState.EMPTY: "⬜",
        }.get(section.state, "❓")
        
        print(f"\n   {state_emoji} {section.title} ({section.state.value})")
        if show_content and section.content:
            # Show first 150 chars of content
            preview = section.content[:150].replace("\n", " ")
            if len(section.content) > 150:
                preview += "..."
            print(f"      {preview}")


async def main():
    """Run the projections demo."""
    
    print_section("CONTENT IS PRIMARY, DOCUMENTS ARE PROJECTIONS")
    print("""
This demo shows:
1. Creating a content pool from collected content
2. Generating document projections from that content  
3. Locking sections to preserve approved content
4. Adding new content and regenerating (locked sections preserved)
5. Multiple projections from the same content
    """)
    
    # =========================================================================
    # Setup
    # =========================================================================
    
    projection_service = ProjectionService()
    
    project_id = "proj_grandma_memoir"
    contributor_id = "contrib_sarah"
    
    # =========================================================================
    # Step 1: Initial content collection
    # =========================================================================
    
    print_section("STEP 1: Collect Initial Content")
    
    # Simulate collected content (from voice recordings, forms, etc.)
    initial_content = [
        ContentItem(
            id="content_001",
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface="voice_recorder",
            content={
                "question": "Tell me about your earliest memories",
                "answer_text": "My earliest memory is of our farmhouse in Iowa. I remember the smell of fresh bread my mother would bake every Sunday morning. The kitchen had yellow curtains that caught the sunlight, and I would sit on a wooden stool watching her work.",
            },
            tags=["childhood", "family", "home"],
        ),
        ContentItem(
            id="content_002",
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface="voice_recorder",
            content={
                "question": "What was school like for you?",
                "answer_text": "I walked two miles to the one-room schoolhouse. Miss Patterson was my teacher for all eight grades. She was strict but fair. I loved learning to read - books opened up a whole new world for me.",
            },
            tags=["education", "childhood"],
        ),
        ContentItem(
            id="content_003",
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface="web_form",
            content={
                "question": "How did you meet your husband?",
                "answer_text": "I met Harold at a church social in 1952. He asked me to dance, and I noticed his kind eyes. We courted for two years before he proposed. We were married 58 years.",
            },
            tags=["relationships", "love", "marriage"],
        ),
    ]
    
    # Add content to the projection service
    for content in initial_content:
        projection_service.add_content_item(content)
        print(f"  ✓ Added: {content.content.get('question', 'content')[:50]}...")
    
    print(f"\n  Content pool now has {len(initial_content)} items")
    
    # =========================================================================
    # Step 2: Generate initial projection
    # =========================================================================
    
    print_section("STEP 2: Generate Thematic Projection")
    
    config = ProjectionConfig(
        style=ProjectionStyle.THEMATIC,
        length=ProjectionLength.STANDARD,
        voice_guidance="warm, nostalgic, and personal",
    )
    
    projection = await projection_service.generate_projection(
        project_id=project_id,
        name="Grandma's Life Story",
        config=config,
    )
    
    print("  Generated projection from content pool")
    print_projection(projection)
    
    # =========================================================================
    # Step 3: User reviews and locks a section
    # =========================================================================
    
    print_section("STEP 3: User Locks a Section")
    
    # Simulate user approving the Family section
    if projection.sections:
        first_section = projection.sections[0]
        
        print(f"\n  User reviews '{first_section.title}' section...")
        print(f"  User says: 'This is perfect! I want to keep it exactly like this.'")
        
        projection_service.lock_section(
            projection_id=projection.id,
            section_id=first_section.id,
            user_id="user_sarah",
            reason="approved - perfect as is",
        )
        
        print(f"\n  🔒 Locked section: {first_section.title}")
    
    print_projection(projection, show_content=False)
    
    # =========================================================================
    # Step 4: More content arrives
    # =========================================================================
    
    print_section("STEP 4: New Content Arrives")
    
    new_content = [
        ContentItem(
            id="content_004",
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface="voice_recorder",
            content={
                "question": "What challenges did you face?",
                "answer_text": "The drought of 1956 nearly destroyed us. We lost most of our crops, and Harold had to take work at the factory in town. Those were hard years, but they taught us resilience. We learned that family is more important than prosperity.",
            },
            tags=["challenges", "resilience", "family"],
        ),
        ContentItem(
            id="content_005",
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.TEXT,
            source_interface="web_form",
            content={
                "question": "What are you most proud of?",
                "answer_text": "My children. All four of them turned out to be good, kind people. That's not about me - they made their own choices - but I like to think Harold and I gave them a strong foundation. Seeing them raise their own families is the greatest gift.",
            },
            tags=["family", "pride", "values"],
        ),
    ]
    
    for content in new_content:
        projection_service.add_content_item(content)
        print(f"  ✓ Added: {content.content.get('question', 'content')[:50]}...")
    
    print(f"\n  Content pool now has 5 items total")
    
    # =========================================================================
    # Step 5: Regenerate projection
    # =========================================================================
    
    print_section("STEP 5: Regenerate Projection (Locked Sections Preserved)")
    
    print("  Regenerating document from updated content pool...")
    print("  (Locked sections will NOT be changed)")
    
    await projection_service.regenerate_projection(projection)
    
    print_projection(projection, show_content=False)
    
    locked = projection.get_locked_sections()
    regenerated = projection.get_regeneratable_sections()
    
    print(f"\n  Summary:")
    print(f"    🔒 Locked sections (preserved): {len(locked)}")
    print(f"    🔄 Regenerated sections: {len(regenerated)}")
    
    # =========================================================================
    # Step 6: Multiple projections from same content
    # =========================================================================
    
    print_section("STEP 6: Multiple Projections from Same Content")
    
    # Create a summary projection
    summary_config = ProjectionConfig(
        style=ProjectionStyle.CHRONOLOGICAL,
        length=ProjectionLength.SUMMARY,
        voice_guidance="concise but warm",
    )
    
    summary = await projection_service.generate_projection(
        project_id=project_id,
        name="Story Summary (2 pages)",
        config=summary_config,
    )
    
    print("  Created alternative projection: Summary version")
    print_projection(summary, show_content=False)
    
    # Show all projections for project
    all_projections = projection_service.get_project_projections(project_id)
    
    print(f"\n  This project now has {len(all_projections)} projections:")
    for proj in all_projections:
        locked_count = len(proj.get_locked_sections())
        print(f"    • {proj.name} ({proj.word_count} words, {locked_count} locked)")
    
    # =========================================================================
    # Step 7: Manual edit with lock
    # =========================================================================
    
    print_section("STEP 7: Manual Edit (User Revises Section)")
    
    if len(projection.sections) > 1:
        section_to_edit = projection.sections[1]
        
        print(f"\n  User manually edits '{section_to_edit.title}' section...")
        
        # Simulate user editing
        projection_service.edit_section(
            projection_id=projection.id,
            section_id=section_to_edit.id,
            new_content="This is my personally crafted version of this section. I've carefully edited the AI-generated content to better reflect my memories and add details the AI couldn't know.",
            lock=True,  # Lock after editing
        )
        
        print(f"  ✏️  User saved edits to: {section_to_edit.title}")
        print(f"  🔒 Section automatically locked to preserve edits")
    
    print_projection(projection, show_content=False)
    
    # =========================================================================
    # Final Status
    # =========================================================================
    
    print_section("FINAL STATE")
    
    print("\n📊 Content Pool:")
    pool = projection_service._content_pools.get(project_id)
    print(f"   Total content items: {pool.total_items}")
    print(f"   Contributors: {pool.contributor_ids}")
    print(f"   Tags: {pool.tags}")
    
    print("\n📄 Document Projections:")
    for proj in all_projections:
        status = proj.get_status()
        print(f"\n   {proj.name}:")
        print(f"      Sections: {status['sections_count']}")
        print(f"      Locked: {status['locked_count']}")
        print(f"      Words: {status['word_count']}")
    
    print("\n" + "=" * 60)
    print("  KEY TAKEAWAY:")
    print("  Content is the source of truth. Documents are views.")
    print("  Lock sections to preserve approved content.")
    print("  Add content anytime - regenerate when ready.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

