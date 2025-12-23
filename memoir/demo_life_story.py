"""
Demo: Life Story Journey - Watch Your Document Evolve

This demo simulates an older person building their life story:
1. Start with childhood memories
2. Add more content about different life stages
3. Watch the document EVOLVE (not just regenerate)
4. Lock sections you love, edit others
5. See version history

Uses real AI (Gemini) when GOOGLE_API_KEY is set.

Run: python -m memoir.demo_life_story
"""

import asyncio
import os
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
            preview = s.content.replace("\n", " ")[:200]
            if len(s.content) > 200:
                preview += "..."
            print(f"      {preview}")


def show_update_options(options: dict):
    """Display available update options."""
    print(f"\n📊 Update Options:")
    print(f"   New content available: {options['has_new_content']}")
    print(f"   New items: {options['new_content_count']}")
    print(f"   Stale sections: {options['stale_section_count']}")
    
    print(f"\n   Available modes:")
    for mode in options['available_modes']:
        print(f"     • {mode['mode']}: {mode['description']}")


def wait_for_input(prompt: str = "Press Enter to continue..."):
    """Wait for user input."""
    input(f"\n⏳ {prompt}")


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


HARDSHIP_CONTENT = [
    {
        "id": "c_006",
        "question": "What challenges did you face in life?",
        "answer": """The drought of 1956 nearly broke us. We'd just bought our own little 
        farm, scraping together every penny. Then the rains stopped. Watched our crops 
        wither, our dreams turning to dust.
        
        Harold took work at the factory in town, coming home exhausted. I took in 
        laundry, watched other people's children. We ate beans and cornbread more nights 
        than I can count. But we never went hungry, and we never gave up.
        
        Lost our second baby in 1959. That was the hardest thing. Harder than any drought. 
        The doctor said these things happen, nothing to be done. Harold held me while I 
        cried for weeks. We almost didn't try again, but then came Johnny, then Sarah, 
        then the twins. Life has a way of giving back what it takes.""",
        "tags": ["hardship", "resilience", "faith"],
    },
]


WISDOM_CONTENT = [
    {
        "id": "c_007",
        "question": "What are you most proud of?",
        "answer": """My children, without question. All four of them turned out to be 
        good, kind people. That's not about me - they made their own choices. But I 
        like to think Harold and I gave them a foundation. We showed them what hard 
        work looks like, what commitment means.
        
        Johnny's a doctor now. Can you imagine? A farm boy's son, a doctor. Sarah 
        teaches third grade - she has Mama's patience. The twins run a business together, 
        still fighting like cats and dogs, still inseparable.
        
        Twelve grandchildren. Three great-grandchildren, with more on the way. When 
        they all come home for Christmas, the house bursts at the seams just like when 
        I was little. The circle continues.""",
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
        help you. Pride is a luxury. Love is a necessity.
        
        I've lived nearly nine decades now. The world has changed in ways I never could 
        have imagined. But people haven't changed. We still need the same things: 
        someone to love, meaningful work, a community to belong to. Don't let the 
        noise of modern life make you forget what matters.""",
        "tags": ["wisdom", "values", "legacy"],
    },
]


# =============================================================================
# Main Demo
# =============================================================================


async def main():
    """Run the life story demo."""
    
    banner("LIFE STORY JOURNEY: WATCH YOUR DOCUMENT EVOLVE")
    
    print("""
    This demo simulates building a life story memoir:
    
    1. Childhood memories → Generate initial document
    2. Add school stories → EVOLVE the document (not regenerate!)
    3. Add love & marriage → See themes emerge
    4. Lock a section → It's perfect, preserve it
    5. Add hardship & wisdom → Document grows intelligently
    6. Compare update modes → See the difference
    
    Using AI: {'✅ Gemini' if os.getenv('GOOGLE_API_KEY') else '❌ Stub (set GOOGLE_API_KEY for real AI)'}
    """)
    
    wait_for_input()
    
    # Initialize
    service = ProjectionService(use_ai=True)
    project_id = "grandmas_story"
    contributor = "grandma"
    
    def add_content(items: list[dict]):
        """Helper to add content items."""
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
            print(f"  ✓ {item['question'][:50]}...")
    
    # =========================================================================
    # Phase 1: Childhood Memories
    # =========================================================================
    
    banner("PHASE 1: CHILDHOOD MEMORIES", "─")
    
    print("\n🎤 Recording childhood memories...")
    add_content(CHILDHOOD_CONTENT)
    
    wait_for_input("Press Enter to generate the initial document...")
    
    section("Generating initial projection...")
    
    config = ProjectionConfig(
        style=ProjectionStyle.THEMATIC,
        length=ProjectionLength.STANDARD,
        voice_guidance="warm, nostalgic, and personal - as if sitting by a fireplace sharing stories",
        suggested_sections=["Early Roots", "Family", "Growing Up"],
        default_update_mode=UpdateMode.EVOLVE,
    )
    
    projection = await service.generate_projection(
        project_id=project_id,
        name="A Life Well Lived",
        config=config,
    )
    
    show_projection(projection)
    
    # =========================================================================
    # Phase 2: School Years
    # =========================================================================
    
    wait_for_input()
    banner("PHASE 2: SCHOOL YEARS", "─")
    
    print("\n🎤 Recording school memories...")
    add_content(SCHOOL_CONTENT)
    
    # Show what update options are available
    options = service.get_update_options(projection.id)
    show_update_options(options)
    
    wait_for_input("Press Enter to EVOLVE the document (not regenerate!)...")
    
    section("Evolving document with new content...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    print(f"\n✨ Document evolved to v{projection.version}")
    show_projection(projection)
    
    # =========================================================================
    # Phase 3: Love & Marriage
    # =========================================================================
    
    wait_for_input()
    banner("PHASE 3: LOVE & MARRIAGE", "─")
    
    print("\n🎤 Recording love story...")
    add_content(LOVE_CONTENT)
    
    wait_for_input("Press Enter to evolve again...")
    
    section("Evolving with love & marriage content...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    show_projection(projection)
    
    # Show themes building up
    if projection.context.themes:
        print("\n🎭 Emerging Themes:")
        for theme in projection.context.themes:
            print(f"   • {theme.theme}: {theme.description[:60]}...")
    
    # =========================================================================
    # Phase 4: Lock a Section
    # =========================================================================
    
    wait_for_input()
    banner("PHASE 4: LOCK A SECTION", "─")
    
    if projection.sections:
        section_to_lock = projection.sections[0]
        
        print(f"\n👀 Reviewing section: '{section_to_lock.title}'")
        print(f"\n{section_to_lock.content[:400]}...")
        
        print("\n\n💭 'This is perfect! I don't want this to change.'")
        
        wait_for_input("Press Enter to lock this section...")
        
        service.lock_section(
            projection.id,
            section_to_lock.id,
            "grandma",
            "Perfect as written - captures the feeling exactly"
        )
        
        print(f"\n🔒 Locked: '{section_to_lock.title}'")
        print("   This section will be preserved in all future updates.")
    
    # =========================================================================
    # Phase 5: Hardship & Wisdom
    # =========================================================================
    
    wait_for_input()
    banner("PHASE 5: HARDSHIP & WISDOM", "─")
    
    print("\n🎤 Recording deeper stories...")
    add_content(HARDSHIP_CONTENT)
    add_content(WISDOM_CONTENT)
    
    print(f"\n📊 Content pool now has {len(service._content_items)} items")
    
    wait_for_input("Press Enter to evolve the document...")
    
    section("Evolving with hardship & wisdom...")
    
    await service.update_projection(projection, UpdateMode.EVOLVE)
    
    show_projection(projection)
    
    # =========================================================================
    # Phase 6: Demonstrate Different Update Modes
    # =========================================================================
    
    wait_for_input()
    banner("UNDERSTANDING UPDATE MODES", "─")
    
    print("""
    The document has evolved through multiple updates. Here's what each mode does:
    
    🔄 EVOLVE (what we used)
       Integrates new content while preserving the document's structure.
       The AI weaves new information into existing sections.
    
    🔃 REGENERATE
       Completely rewrites unlocked sections from scratch.
       Use when you want a fresh perspective.
    
    🔁 REFRESH
       Only updates sections that have new relevant content.
       Minimal changes, just adds what's new.
    
    ➕ APPEND
       Adds new content to the end of existing sections.
       Preserves everything, just extends.
    """)
    
    # =========================================================================
    # Phase 7: Version History
    # =========================================================================
    
    wait_for_input()
    banner("VERSION HISTORY", "─")
    
    print(f"\n📜 Document: {projection.name}")
    print(f"   Current version: {projection.version}")
    print(f"\n   Version history:")
    
    for vh in projection.version_history[-5:]:
        mode = vh.update_mode.value if vh.update_mode else "n/a"
        print(f"   • v{vh.version} - {vh.trigger} ({mode}) - {vh.change_summary}")
    
    if projection.sections:
        print(f"\n📝 Section history for '{projection.sections[0].title}':")
        section = projection.sections[0]
        print(f"   Current: v{section.version}")
        for sh in section.history[-3:]:
            print(f"   • v{sh.version} - {sh.trigger}")
    
    # =========================================================================
    # Final Output
    # =========================================================================
    
    wait_for_input()
    banner("FINAL DOCUMENT")
    
    print(projection.get_full_text())
    
    # =========================================================================
    # Summary
    # =========================================================================
    
    banner("SUMMARY")
    
    print(f"""
    📖 Created: {projection.name}
    📊 Final version: v{projection.version}
    📝 Sections: {len(projection.sections)}
    📏 Word count: {projection.word_count}
    🔒 Locked sections: {len(projection.get_locked_sections())}
    🎭 Themes discovered: {len(projection.context.themes)}
    
    The document EVOLVED intelligently as content was added:
    - New memories were woven into existing narrative
    - Locked sections were preserved
    - Themes emerged naturally from the content
    - Full version history maintained
    
    Try the API: uvicorn memoir.api.app:app --reload
    """)


if __name__ == "__main__":
    asyncio.run(main())

