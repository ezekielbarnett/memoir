"""
Demo: Life Story Journey - Watch Your Document Evolve (Auto-run version)

This runs automatically without requiring user input.
Uses real AI (Gemini) when GEMINI_API_KEY/GOOGLE_API_KEY is set.

Run: python -m memoir.demo_life_story_auto
"""

import asyncio
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from memoir.core.models import ContentItem, ContentType
from memoir.core.projections import (
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    UpdateMode,
    SectionState,
)
from memoir.services.projection import ProjectionService


# =============================================================================
# Helper Functions
# =============================================================================


def banner(text: str, char: str = "="):
    """Print a banner."""
    width = 70
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)


def section(text: str):
    """Print a section header."""
    print(f"\n{'─' * 50}")
    print(f"  {text}")
    print(f"{'─' * 50}")


def show_projection(projection, verbose: bool = True):
    """Display a projection nicely."""
    print(f"\n📖 {projection.name} (v{projection.version})")
    print(f"   Words: {projection.word_count} | Sections: {len(projection.sections)}")
    
    if projection.context.themes:
        themes = ", ".join(t.theme for t in projection.context.themes[:4])
        print(f"   Themes: {themes}")
    
    for s in projection.sections:
        emoji = {
            SectionState.GENERATED: "🔄",
            SectionState.LOCKED: "🔒",
            SectionState.DRAFT: "✏️",
            SectionState.EMPTY: "⬜",
        }.get(s.state, "❓")
        
        print(f"\n   {emoji} {s.title} (v{s.version})")
        
        if verbose and s.content:
            preview = s.content.replace("\n", " ")[:300]
            if len(s.content) > 300:
                preview += "..."
            print(f"      {preview}")


# =============================================================================
# Life Story Content
# =============================================================================


CHILDHOOD_CONTENT = [
    {
        "id": "c_001",
        "question": "What are your earliest childhood memories?",
        "answer": """My earliest memory is from when I was about four years old, sitting on the 
        back porch of our farmhouse watching the fireflies come out at dusk. My father would 
        come in from the fields, dusty and tired, and sweep me up onto his shoulders. The 
        smell of earth and sweat was comforting. We didn't have much, but we had each other.
        
        The farmhouse had a big oak tree out front that my grandfather planted. I used to 
        climb it with my older brother Tommy, hiding from our chores. Mama would ring the 
        dinner bell, and we'd scramble down, pretending we'd been helping all along.""",
        "tags": ["childhood", "family", "home"],
    },
    {
        "id": "c_002",
        "question": "Tell me about your family growing up.",
        "answer": """We were a family of six - Mama, Papa, Tommy, me, and my two younger 
        sisters Mary and Ruth. Tommy was my hero and my rival. We fought like cats and 
        dogs but were inseparable. Mary was the quiet one, always reading. Ruth was the 
        baby, spoiled rotten by all of us.
        
        Papa worked the farm from sunup to sundown. He wasn't a man of many words, but 
        when he spoke, you listened. Mama ran everything else - the house, us kids, the 
        church activities. She could stretch a dollar further than anyone I've known since.
        
        Sundays were sacred. Church in the morning, then the whole family would gather 
        for dinner. Aunts, uncles, cousins - the house would be bursting with people and 
        food and laughter.""",
        "tags": ["family", "childhood", "values"],
    },
]


SCHOOL_CONTENT = [
    {
        "id": "c_003",
        "question": "What was school like for you?",
        "answer": """I walked two miles to the one-room schoolhouse, rain or shine. Miss 
        Patterson taught all eight grades - she was strict but fair. She's the one who 
        taught me to love reading. She'd lend me books from her personal collection.
        
        I wasn't the best student - always getting distracted looking out the window or 
        passing notes. But I loved history. The stories of people who came before, who 
        faced hardships and prevailed. I think that's what gave me strength later in life.
        
        High school meant a bus ride to town. That's where I met Harold, actually - on 
        that bus. But that's getting ahead of myself.""",
        "tags": ["education", "formative", "growth"],
    },
]


LOVE_CONTENT = [
    {
        "id": "c_004",
        "question": "How did you meet your spouse?",
        "answer": """Harold sat three rows behind me on the school bus. For months, I didn't 
        even know he existed. Then one day, my books went flying when the bus hit a pothole, 
        and he helped me pick them up. He had the kindest eyes I'd ever seen.
        
        We started talking on those bus rides. He was shy, but funny once you got to know 
        him. He'd bring me wildflowers he'd picked on his walk to the bus stop. Little 
        things, but they meant the world.
        
        We courted for two years. Papa didn't approve at first - Harold's family was 
        poor, even by our standards. But Harold worked hard, saved every penny. When he 
        finally asked Papa for my hand, he had a plan for our future mapped out. Papa 
        couldn't say no to that kind of determination.""",
        "tags": ["love", "romance", "relationships"],
    },
    {
        "id": "c_005",
        "question": "What was your wedding like?",
        "answer": """We married in June of 1952, in the little white church where I'd been 
        baptized. I wore Mama's dress, taken in and altered. Mary caught the bouquet - 
        she married the following year.
        
        We couldn't afford a honeymoon, so we spent our first night as husband and wife 
        in a cabin Harold had borrowed from his uncle. Just one night, then back to work. 
        But those 24 hours felt like a lifetime of happiness compressed into a single day.
        
        We were married for 58 years. Lost him in 2010. Not a day goes by I don't think 
        of those kind eyes on the school bus.""",
        "tags": ["love", "marriage", "loss"],
    },
]


WISDOM_CONTENT = [
    {
        "id": "c_006",
        "question": "What challenges did you face in life?",
        "answer": """The drought of 1956 nearly broke us. We'd just bought our own little 
        farm, scraping together every penny. Then the rains stopped. Watched our crops 
        wither, our dreams turning to dust.
        
        Harold took work at the factory in town, coming home exhausted. I took in 
        laundry, watched other people's children. We ate beans and cornbread more nights 
        than I can count. But we never went hungry, and we never gave up.""",
        "tags": ["hardship", "resilience", "faith"],
    },
    {
        "id": "c_007",
        "question": "What are you most proud of?",
        "answer": """My children, without question. All four of them turned out to be 
        good, kind people. Johnny's a doctor now. Can you imagine? A farm boy's son, 
        a doctor. Sarah teaches third grade. The twins run a business together.
        
        Twelve grandchildren. Three great-grandchildren. When they all come home for 
        Christmas, the house bursts at the seams just like when I was little.""",
        "tags": ["family", "legacy", "pride"],
    },
    {
        "id": "c_008",
        "question": "What advice would you give to younger generations?",
        "answer": """Don't wait for happiness to find you. Build it yourself, day by day, 
        with your own two hands. It's not in the big moments - it's in the small ones. 
        Sunday dinners. Bedtime stories. Dancing in the kitchen when a song you love 
        comes on the radio.
        
        And when hardship comes - and it will come - don't face it alone. Let people 
        help you. Pride is a luxury. Love is a necessity.""",
        "tags": ["wisdom", "values", "legacy"],
    },
]


# =============================================================================
# Main Demo
# =============================================================================


async def main():
    """Run the life story demo."""
    
    banner("LIFE STORY JOURNEY: DOCUMENT EVOLUTION DEMO")
    
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    print(f"""
    This demo shows how a life story document EVOLVES as content is added.
    
    Using AI: {'✅ Gemini (real AI generation!)' if api_key else '❌ Stub mode (set GEMINI_API_KEY for real AI)'}
    """)
    
    # Initialize
    service = ProjectionService(use_ai=True)
    project_id = "grandmas_story"
    contributor = "grandma"
    
    def add_content(items: list[dict], label: str):
        """Helper to add content items."""
        print(f"\n🎤 Adding {label}...")
        for item in items:
            content = ContentItem(
                id=item["id"],
                project_id=project_id,
                contributor_id=contributor,
                content_type=ContentType.STRUCTURED_QA,
                source_interface="voice_recorder",
                content={
                    "question_text": item["question"],
                    "answer_text": item["answer"],
                },
                tags=item.get("tags", []),
            )
            service.add_content_item(content)
            print(f"   ✓ {item['question'][:40]}...")
    
    # =========================================================================
    # Phase 1: Initial content and generation
    # =========================================================================
    
    banner("PHASE 1: CHILDHOOD MEMORIES → INITIAL DOCUMENT", "─")
    
    add_content(CHILDHOOD_CONTENT, "childhood memories")
    
    section("Generating initial document...")
    
    config = ProjectionConfig(
        style=ProjectionStyle.THEMATIC,
        length=ProjectionLength.STANDARD,
        voice_guidance="warm, nostalgic, and personal - capturing the feeling of sitting by a fireplace sharing stories",
        suggested_sections=["Early Roots", "Family Ties", "Growing Up"],
        default_update_mode=UpdateMode.EVOLVE,
    )
    
    projection = await service.generate_projection(
        project_id=project_id,
        name="A Life Well Lived",
        config=config,
    )
    
    show_projection(projection)
    
    # =========================================================================
    # Phase 2: Add school content, EVOLVE (not regenerate!)
    # =========================================================================
    
    banner("PHASE 2: SCHOOL YEARS → EVOLVE DOCUMENT", "─")
    
    add_content(SCHOOL_CONTENT, "school memories")
    
    section("Evolving document (integrating new content into existing structure)...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    print(f"\n✨ Document evolved to v{projection.version}")
    show_projection(projection, verbose=False)
    
    # =========================================================================
    # Phase 3: Love story, continue evolving
    # =========================================================================
    
    banner("PHASE 3: LOVE & MARRIAGE → EVOLVE AGAIN", "─")
    
    add_content(LOVE_CONTENT, "love story")
    
    section("Evolving with love & marriage content...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    show_projection(projection, verbose=False)
    
    # Show emerging themes
    if projection.context.themes:
        print("\n🎭 Themes AI has discovered:")
        for theme in projection.context.themes[:5]:
            desc = theme.description[:80] if theme.description else ""
            print(f"   • {theme.theme}: {desc}...")
    
    # =========================================================================
    # Phase 4: Lock a section
    # =========================================================================
    
    banner("PHASE 4: LOCK A PERFECT SECTION", "─")
    
    if projection.sections:
        section_to_lock = projection.sections[0]
        
        print(f"\n👀 Section '{section_to_lock.title}' is perfect!")
        print("   Locking it to preserve it in future updates...")
        
        service.lock_section(
            projection.id,
            section_to_lock.id,
            "grandma",
            "Perfect as written"
        )
        
        print(f"\n   🔒 LOCKED: '{section_to_lock.title}'")
    
    # =========================================================================
    # Phase 5: Add final content, evolve again
    # =========================================================================
    
    banner("PHASE 5: WISDOM & LEGACY → FINAL EVOLUTION", "─")
    
    add_content(WISDOM_CONTENT, "hardship and wisdom")
    
    section("Final evolution (locked sections will be preserved)...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    show_projection(projection)
    
    # =========================================================================
    # Version History
    # =========================================================================
    
    banner("VERSION HISTORY", "─")
    
    print(f"\n📜 Document has evolved through {projection.version} versions:")
    for vh in projection.version_history:
        mode = vh.update_mode.value if vh.update_mode else "n/a"
        print(f"   v{vh.version}: {vh.trigger} ({mode}) - {vh.word_count} words")
    
    # =========================================================================
    # Final Document
    # =========================================================================
    
    banner("FINAL DOCUMENT")
    
    print(projection.get_full_text())
    
    # =========================================================================
    # Summary
    # =========================================================================
    
    banner("SUMMARY")
    
    locked_sections = projection.get_locked_sections()
    
    print(f"""
    📖 Document: {projection.name}
    📊 Final version: v{projection.version}
    📝 Sections: {len(projection.sections)}
    📏 Word count: {projection.word_count}
    🔒 Locked sections: {len(locked_sections)} ({', '.join(s.title for s in locked_sections) or 'none'})
    🎭 Themes: {len(projection.context.themes)}
    
    ✨ Key insight: The document EVOLVED intelligently:
       - New content was woven into the narrative
       - Locked sections were preserved untouched  
       - Themes emerged naturally from the content
       - Full version history maintained
    
    🚀 Try the interactive API next:
       uvicorn memoir.api.app:app --reload
       Then visit: http://localhost:8000/docs
    """)


if __name__ == "__main__":
    asyncio.run(main())

