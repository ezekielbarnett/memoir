"""
Projection Service - Generates and evolves documents from content pools.

This service transforms raw content into structured documents.
It respects locked sections, supports multiple update modes, and
maintains version history.

Key responsibilities:
- Generate initial projection from content
- Evolve/update sections with new content (respecting locks)
- Support different update modes (regenerate, evolve, refresh)
- Maintain narrative context for coherent storytelling
- Track version history
"""

from __future__ import annotations

from typing import Any

from memoir.core.events import Event
from memoir.core.models import ContentItem
from memoir.core.projections import (
    ContentPool,
    DocumentProjection,
    ProjectedSection,
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    SectionState,
    UpdateMode,
    NarrativeContext,
    DiscoveredTheme,
)
from memoir.core.registry import get_registry
from memoir.services.base import Service


# Try to import AI service - gracefully degrade if not configured
try:
    from memoir.services.ai import MemoirAI, configure_lm
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    MemoirAI = None


class ProjectionService(Service):
    """
    Service that generates and maintains document projections.
    
    Projections are computed views of the content pool. This service:
    - Creates new projections with specified configurations
    - Updates projections when content changes (multiple modes)
    - Respects locked sections (won't overwrite)
    - Maintains narrative context for coherent AI generation
    - Tracks version history
    
    Update Modes:
    - REGENERATE: Full regeneration of unlocked sections
    - EVOLVE: Integrate new content while preserving structure
    - REFRESH: Only update stale sections
    - APPEND: Add new content to existing sections
    """
    
    @property
    def service_id(self) -> str:
        return "projection"
    
    @property
    def subscribes_to(self) -> list[str]:
        return [
            "content.created",  # New content → maybe update projections
            "projection.generate",  # Explicit generation request
            "projection.update",  # Update with specified mode
            "projection.regenerate",  # Full regeneration (legacy compat)
            "projection.regenerate_section",  # Regenerate single section
        ]
    
    def __init__(self, use_ai: bool = True):
        self.registry = get_registry()
        
        # Storage (in production, would use StorageProvider)
        self._content_pools: dict[str, ContentPool] = {}  # project_id -> pool
        self._projections: dict[str, DocumentProjection] = {}  # projection_id -> projection
        self._project_projections: dict[str, list[str]] = {}  # project_id -> projection_ids
        
        # Content items cache (in production, would query content store)
        self._content_items: dict[str, ContentItem] = {}  # content_id -> item
        
        # AI service (optional - gracefully degrades to stubs)
        self._ai: MemoirAI | None = None
        self._use_ai = use_ai and AI_AVAILABLE
        
        if self._use_ai:
            try:
                configure_lm()  # Configure from env vars
                self._ai = MemoirAI()
            except Exception as e:
                print(f"⚠️  AI not configured: {e}. Using stub generation.")
                self._ai = None
    
    async def handle(self, event: Event) -> list[Event]:
        """Handle projection-related events."""
        if event.event_type == "content.created":
            return await self._handle_content_created(event)
        elif event.event_type == "projection.generate":
            return await self._handle_generate(event)
        elif event.event_type == "projection.update":
            return await self._handle_update(event)
        elif event.event_type == "projection.regenerate":
            return await self._handle_regenerate(event)
        elif event.event_type == "projection.regenerate_section":
            return await self._handle_regenerate_section(event)
        
        return []
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    async def _handle_content_created(self, event: Event) -> list[Event]:
        """Handle new content - add to pool and maybe update projections."""
        project_id = event.project_id
        content_id = event.payload.get("content_id", "")
        contributor_id = event.contributor_id or ""
        
        # Get or create content pool
        pool = self._get_or_create_pool(project_id)
        
        # Add to pool
        tags = event.payload.get("tags", [])
        pool.add_content(content_id, contributor_id, tags)
        
        # Check if any projections should auto-update
        events = []
        projection_ids = self._project_projections.get(project_id, [])
        
        for proj_id in projection_ids:
            projection = self._projections.get(proj_id)
            if projection and projection.config.auto_update_on_content:
                # Auto-update with configured mode
                await self.update_projection(
                    projection,
                    projection.config.default_update_mode,
                )
                events.append(Event(
                    event_type="projection.auto_updated",
                    project_id=project_id,
                    payload={
                        "projection_id": proj_id,
                        "update_mode": projection.config.default_update_mode.value,
                        "content_id": content_id,
                    },
                    correlation_id=event.correlation_id,
                    causation_id=event.id,
                ))
            else:
                # Just notify that projection may be stale
                events.append(Event(
                    event_type="projection.content_added",
                    project_id=project_id,
                    payload={
                        "projection_id": proj_id,
                        "content_id": content_id,
                        "is_stale": True,
                    },
                    correlation_id=event.correlation_id,
                    causation_id=event.id,
                ))
        
        return events
    
    async def _handle_generate(self, event: Event) -> list[Event]:
        """Generate a new projection."""
        project_id = event.project_id
        name = event.payload.get("name", "Document")
        config_dict = event.payload.get("config", {})
        
        # Parse config
        config = self._parse_config(config_dict)
        
        # Generate projection
        projection = await self.generate_projection(project_id, name, config)
        
        return [Event(
            event_type="projection.generated",
            project_id=project_id,
            payload={
                "projection_id": projection.id,
                "name": projection.name,
                "version": projection.version,
                "sections_count": len(projection.sections),
                "word_count": projection.word_count,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_update(self, event: Event) -> list[Event]:
        """Update a projection with specified mode."""
        projection_id = event.payload.get("projection_id", "")
        mode_str = event.payload.get("mode", "evolve")
        section_ids = event.payload.get("section_ids")  # Optional: specific sections
        
        projection = self._projections.get(projection_id)
        if not projection:
            return []
        
        mode = UpdateMode(mode_str)
        
        if section_ids:
            # Update specific sections
            for section_id in section_ids:
                section = projection.get_section(section_id)
                if section and section.can_regenerate:
                    await self._update_section(projection, section, mode)
        else:
            # Update all eligible sections
            await self.update_projection(projection, mode)
        
        return [Event(
            event_type="projection.updated",
            project_id=projection.project_id,
            payload={
                "projection_id": projection.id,
                "update_mode": mode.value,
                "version": projection.version,
                "sections_updated": len(projection.get_regeneratable_sections()),
                "sections_locked": len(projection.get_locked_sections()),
                "word_count": projection.word_count,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_regenerate(self, event: Event) -> list[Event]:
        """Full regeneration of a projection (legacy compat)."""
        projection_id = event.payload.get("projection_id", "")
        
        projection = self._projections.get(projection_id)
        if not projection:
            return []
        
        await self.update_projection(projection, UpdateMode.REGENERATE)
        
        return [Event(
            event_type="projection.regenerated",
            project_id=projection.project_id,
            payload={
                "projection_id": projection.id,
                "version": projection.version,
                "sections_regenerated": len(projection.get_regeneratable_sections()),
                "sections_locked": len(projection.get_locked_sections()),
                "word_count": projection.word_count,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_regenerate_section(self, event: Event) -> list[Event]:
        """Regenerate a single section."""
        projection_id = event.payload.get("projection_id", "")
        section_id = event.payload.get("section_id", "")
        mode_str = event.payload.get("mode", "regenerate")
        
        projection = self._projections.get(projection_id)
        if not projection:
            return []
        
        section = projection.get_section(section_id)
        if not section or not section.can_regenerate:
            return []
        
        mode = UpdateMode(mode_str)
        await self._update_section(projection, section, mode)
        
        return [Event(
            event_type="projection.section_updated",
            project_id=projection.project_id,
            payload={
                "projection_id": projection.id,
                "section_id": section.id,
                "section_title": section.title,
                "update_mode": mode.value,
                "version": section.version,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    # =========================================================================
    # Core Projection Logic
    # =========================================================================
    
    async def generate_projection(
        self,
        project_id: str,
        name: str,
        config: ProjectionConfig,
    ) -> DocumentProjection:
        """
        Generate a new projection from the content pool.
        
        This is the main entry point for creating a document view.
        """
        # Get content pool
        pool = self._get_or_create_pool(project_id)
        
        # Get content items
        content_ids = pool.get_filtered_ids(
            contributor_filter=config.contributor_filter,
            tag_filter=config.tag_filter,
        )
        content_items = [
            self._content_items[cid]
            for cid in content_ids
            if cid in self._content_items
        ]
        
        # Create projection
        projection = DocumentProjection(
            project_id=project_id,
            name=name,
            config=config,
        )
        
        # Extract themes and build context first
        projection.context = await self._build_narrative_context(content_items)
        
        # Generate sections based on style
        if config.style == ProjectionStyle.CHRONOLOGICAL:
            sections = await self._generate_chronological(content_items, config, projection.context)
        elif config.style == ProjectionStyle.THEMATIC:
            sections = await self._generate_thematic(content_items, config, projection.context)
        elif config.style == ProjectionStyle.BY_CONTRIBUTOR:
            sections = await self._generate_by_contributor(content_items, config, projection.context)
        else:
            sections = await self._generate_thematic(content_items, config, projection.context)
        
        # Add sections to projection
        for section in sections:
            projection.add_section(section)
        
        # Mark as generated
        projection.mark_updated(content_ids, UpdateMode.REGENERATE, "Initial generation")
        
        # Store
        self._projections[projection.id] = projection
        if project_id not in self._project_projections:
            self._project_projections[project_id] = []
        self._project_projections[project_id].append(projection.id)
        
        return projection
    
    async def update_projection(
        self,
        projection: DocumentProjection,
        mode: UpdateMode,
    ) -> None:
        """
        Update a projection based on the specified mode.
        
        Modes:
        - REGENERATE: Full regeneration of unlocked sections
        - EVOLVE: Integrate new content while preserving structure
        - REFRESH: Only update stale sections
        - APPEND: Add new content to existing sections
        """
        pool = self._content_pools.get(projection.project_id)
        if not pool:
            return
        
        content_ids = pool.get_filtered_ids(
            contributor_filter=projection.config.contributor_filter,
            tag_filter=projection.config.tag_filter,
        )
        content_items = [
            self._content_items[cid]
            for cid in content_ids
            if cid in self._content_items
        ]
        
        # Update narrative context with new content
        new_content_ids = pool.get_new_content_ids(projection.content_snapshot_ids)
        if new_content_ids:
            new_items = [
                self._content_items[cid]
                for cid in new_content_ids
                if cid in self._content_items
            ]
            await self._update_narrative_context(projection.context, new_items)
        
        # Get sections to update based on mode
        if mode == UpdateMode.REGENERATE:
            sections_to_update = projection.get_regeneratable_sections()
        elif mode == UpdateMode.REFRESH:
            sections_to_update = projection.get_stale_sections(content_ids)
        else:  # EVOLVE or APPEND
            sections_to_update = projection.get_stale_sections(content_ids)
        
        # Update each section
        for section in sections_to_update:
            await self._update_section(projection, section, mode, content_items)
        
        # Build change summary
        change_summary = f"{mode.value}: updated {len(sections_to_update)} sections"
        if new_content_ids:
            change_summary += f" with {len(new_content_ids)} new content items"
        
        projection.mark_updated(content_ids, mode, change_summary)
    
    async def _update_section(
        self,
        projection: DocumentProjection,
        section: ProjectedSection,
        mode: UpdateMode,
        content_items: list[ContentItem] | None = None,
    ) -> None:
        """Update a single section based on mode."""
        if content_items is None:
            pool = self._content_pools.get(projection.project_id)
            if pool:
                content_items = [
                    self._content_items[cid]
                    for cid in pool.content_ids
                    if cid in self._content_items
                ]
            else:
                content_items = []
        
        if mode == UpdateMode.REGENERATE:
            # Full regeneration - replace content entirely
            new_content = await self._generate_section_content(
                section.title,
                content_items,
                projection.config,
                projection.context,
            )
            section.update_content(
                new_content,
                [c.id for c in content_items],
                "regeneration",
            )
            
        elif mode == UpdateMode.EVOLVE:
            # Evolve - integrate new content while preserving structure
            new_content = await self._evolve_section_content(
                section.title,
                section.content,
                content_items,
                projection.config,
                projection.context,
            )
            section.update_content(
                new_content,
                [c.id for c in content_items],
                "evolution",
            )
            
        elif mode == UpdateMode.APPEND:
            # Append - add new content at the end
            # Get only new items
            new_items = [
                c for c in content_items
                if c.id not in section.last_content_snapshot
            ]
            if new_items:
                appended = await self._generate_section_content(
                    f"additional content for {section.title}",
                    new_items,
                    projection.config,
                    projection.context,
                )
                new_content = f"{section.content}\n\n{appended}"
                section.update_content(
                    new_content,
                    [c.id for c in content_items],
                    "append",
                )
                
        elif mode == UpdateMode.REFRESH:
            # Refresh - only if stale, full regeneration
            if section.is_stale([c.id for c in content_items]):
                new_content = await self._generate_section_content(
                    section.title,
                    content_items,
                    projection.config,
                    projection.context,
                )
                section.update_content(
                    new_content,
                    [c.id for c in content_items],
                    "refresh",
                )
    
    # =========================================================================
    # Narrative Context
    # =========================================================================
    
    async def _build_narrative_context(
        self,
        content_items: list[ContentItem],
    ) -> NarrativeContext:
        """Build initial narrative context from content."""
        context = NarrativeContext()
        
        if not content_items:
            return context
        
        # Extract all text
        texts = self._extract_texts(content_items)
        all_text = "\n\n".join(texts)
        
        if self._ai:
            try:
                result = self._ai.extract_themes(all_text)
                
                # Convert themes
                for theme_data in result.get("themes", []):
                    if isinstance(theme_data, str):
                        context.add_theme(DiscoveredTheme(theme=theme_data))
                    elif isinstance(theme_data, dict):
                        context.add_theme(DiscoveredTheme(
                            theme=theme_data.get("theme", ""),
                            description=theme_data.get("description", ""),
                        ))
                
                context.key_facts = result.get("key_facts", {})
                context.suggested_topics = result.get("suggested_topics", [])
                context.emotional_tone = result.get("emotional_tone", "neutral")
                
            except Exception as e:
                print(f"⚠️  Theme extraction failed: {e}")
        
        # Fallback: stub extraction
        if not context.themes:
            context.themes = self._stub_extract_themes(texts)
        
        context.update()
        return context
    
    async def _update_narrative_context(
        self,
        context: NarrativeContext,
        new_items: list[ContentItem],
    ) -> None:
        """Update narrative context with new content."""
        if not new_items:
            return
        
        texts = self._extract_texts(new_items)
        all_text = "\n\n".join(texts)
        
        if self._ai:
            try:
                existing_themes = [t.theme for t in context.themes]
                result = self._ai.extract_themes(all_text, existing_themes)
                
                for theme_data in result.get("themes", []):
                    if isinstance(theme_data, str):
                        context.add_theme(DiscoveredTheme(
                            theme=theme_data,
                            source_content_ids=[c.id for c in new_items],
                        ))
                    elif isinstance(theme_data, dict):
                        context.add_theme(DiscoveredTheme(
                            theme=theme_data.get("theme", ""),
                            description=theme_data.get("description", ""),
                            source_content_ids=[c.id for c in new_items],
                        ))
                
                # Merge key facts
                context.key_facts.update(result.get("key_facts", {}))
                
                # Add new suggested topics
                for topic in result.get("suggested_topics", []):
                    if topic not in context.suggested_topics:
                        context.suggested_topics.append(topic)
                
            except Exception as e:
                print(f"⚠️  Context update failed: {e}")
        
        context.update()
    
    # =========================================================================
    # Section Generation by Style
    # =========================================================================
    
    async def _generate_chronological(
        self,
        content_items: list[ContentItem],
        config: ProjectionConfig,
        context: NarrativeContext,
    ) -> list[ProjectedSection]:
        """Generate sections organized chronologically."""
        sections = []
        
        if content_items:
            section = ProjectedSection(
                title="The Story",
                content=await self._generate_section_content(
                    "chronological narrative",
                    content_items,
                    config,
                    context,
                ),
                state=SectionState.GENERATED,
                source_content_ids=[c.id for c in content_items],
            )
            sections.append(section)
        
        return sections
    
    async def _generate_thematic(
        self,
        content_items: list[ContentItem],
        config: ProjectionConfig,
        context: NarrativeContext,
    ) -> list[ProjectedSection]:
        """Generate sections organized by themes."""
        sections = []
        
        # If suggested sections provided, use those
        if config.suggested_sections:
            section_titles = [s.title() for s in config.suggested_sections]
        elif context.themes:
            # Use discovered themes
            section_titles = [t.theme.title() for t in context.themes[:config.max_sections]]
        else:
            # Auto-discover themes (stub)
            section_titles = self._stub_section_titles(content_items)
        
        # Generate content for each section
        for i, title in enumerate(section_titles):
            content = await self._generate_section_content(
                title,
                content_items,
                config,
                context,
            )
            
            section = ProjectedSection(
                title=title,
                content=content,
                state=SectionState.GENERATED if content else SectionState.EMPTY,
                source_content_ids=[c.id for c in content_items],
                order=i,
            )
            sections.append(section)
        
        return sections
    
    async def _generate_by_contributor(
        self,
        content_items: list[ContentItem],
        config: ProjectionConfig,
        context: NarrativeContext,
    ) -> list[ProjectedSection]:
        """Generate sections organized by contributor."""
        by_contributor: dict[str, list[ContentItem]] = {}
        for item in content_items:
            if item.contributor_id not in by_contributor:
                by_contributor[item.contributor_id] = []
            by_contributor[item.contributor_id].append(item)
        
        sections = []
        for i, (contributor_id, items) in enumerate(by_contributor.items()):
            section = ProjectedSection(
                title=f"From Contributor {contributor_id[:8]}",
                content=await self._generate_section_content(
                    f"contributions from {contributor_id}",
                    items,
                    config,
                    context,
                ),
                state=SectionState.GENERATED,
                source_content_ids=[c.id for c in items],
                order=i,
            )
            sections.append(section)
        
        return sections
    
    # =========================================================================
    # Content Generation
    # =========================================================================
    
    async def _generate_section_content(
        self,
        section_topic: str,
        content_items: list[ContentItem],
        config: ProjectionConfig,
        context: NarrativeContext,
    ) -> str:
        """Generate prose for a section."""
        if not content_items:
            return ""
        
        texts = self._extract_texts(content_items)
        if not texts:
            return ""
        
        raw_content = "\n\n".join(texts)
        
        # Build context string
        context_str = context.summary
        if context.themes:
            theme_names = ", ".join(t.theme for t in context.themes[:3])
            context_str += f"\n\nKey themes: {theme_names}"
        
        if self._ai:
            try:
                length_map = {
                    ProjectionLength.SUMMARY: "brief",
                    ProjectionLength.STANDARD: "standard",
                    ProjectionLength.COMPREHENSIVE: "detailed",
                }
                
                result = self._ai.generate_section(
                    title=section_topic,
                    content=raw_content,
                    style=config.voice_guidance or "warm and engaging",
                    context=context_str,
                    length=length_map.get(config.length, "standard"),
                )
                return result["content"]
            except Exception as e:
                print(f"⚠️  AI generation failed: {e}. Using stub.")
        
        # Stub fallback
        return self._stub_generate_section(section_topic, texts, config)
    
    async def _evolve_section_content(
        self,
        section_topic: str,
        existing_content: str,
        content_items: list[ContentItem],
        config: ProjectionConfig,
        context: NarrativeContext,
    ) -> str:
        """Evolve existing content by integrating new information."""
        if not content_items:
            return existing_content
        
        texts = self._extract_texts(content_items)
        new_content = "\n\n".join(texts)
        
        if self._ai and existing_content:
            try:
                result = self._ai.regenerate_section(
                    title=section_topic,
                    existing_content=existing_content,
                    new_content=new_content,
                    style=config.voice_guidance or "warm and engaging",
                )
                return result
            except Exception as e:
                print(f"⚠️  AI evolution failed: {e}. Using stub.")
        
        # Stub: just append
        if existing_content:
            return f"{existing_content}\n\n---\n\n*[New content integrated:]*\n\n{self._stub_generate_section(section_topic, texts, config)}"
        return self._stub_generate_section(section_topic, texts, config)
    
    def _extract_texts(self, content_items: list[ContentItem]) -> list[str]:
        """Extract text from content items."""
        texts = []
        for item in content_items:
            content = item.content
            if "answer_text" in content:
                q = content.get("question_text", "")
                a = content["answer_text"]
                texts.append(f"Q: {q}\nA: {a}" if q else a)
            elif "text" in content:
                texts.append(content["text"])
        return texts
    
    def _stub_generate_section(
        self,
        section_topic: str,
        texts: list[str],
        config: ProjectionConfig,
    ) -> str:
        """Stub generation when AI is not available."""
        n_items = len(texts)
        preview = texts[0][:200] + "..." if texts and len(texts[0]) > 200 else texts[0] if texts else ""
        
        length_desc = {
            ProjectionLength.SUMMARY: "brief",
            ProjectionLength.STANDARD: "standard",
            ProjectionLength.COMPREHENSIVE: "comprehensive",
        }.get(config.length, "standard")
        
        return f"""*[AI-generated {length_desc} section about "{section_topic}"]*

Based on {n_items} content items.

{preview}

---

*[Configure GOOGLE_API_KEY in .env to enable real AI generation with Gemini.]*
"""
    
    def _stub_extract_themes(self, texts: list[str]) -> list[DiscoveredTheme]:
        """Discover themes in content (stub)."""
        if not texts:
            return []
        
        all_text = " ".join(texts).lower()
        themes = []
        
        theme_keywords = {
            "Family": ["family", "mother", "father", "parent", "sibling"],
            "Education": ["school", "learn", "teacher", "study"],
            "Career": ["work", "job", "career", "profession"],
            "Friendship": ["friend", "together", "companion"],
        }
        
        for theme_name, keywords in theme_keywords.items():
            matches = [kw for kw in keywords if kw in all_text]
            if len(matches) >= 2:
                themes.append(DiscoveredTheme(
                    theme=theme_name,
                    description=f"Detected via keywords: {', '.join(matches)}",
                    strength=min(1.0, len(matches) * 0.25),
                ))
        
        return themes[:5]
    
    def _stub_section_titles(self, content_items: list[ContentItem]) -> list[str]:
        """Generate section titles based on content (stub)."""
        if not content_items:
            return ["Introduction", "Story", "Reflections"]
        
        texts = self._extract_texts(content_items)
        all_text = " ".join(texts).lower()
        
        titles = []
        if any(word in all_text for word in ["family", "mother", "father"]):
            titles.append("Family")
        if any(word in all_text for word in ["school", "education", "learn"]):
            titles.append("Education")
        if any(word in all_text for word in ["work", "career", "job"]):
            titles.append("Career")
        if any(word in all_text for word in ["friend", "friendship"]):
            titles.append("Friendships")
        
        if not titles:
            titles = ["Memories", "Reflections"]
        
        return titles
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _get_or_create_pool(self, project_id: str) -> ContentPool:
        """Get or create content pool for a project."""
        if project_id not in self._content_pools:
            self._content_pools[project_id] = ContentPool(project_id=project_id)
        return self._content_pools[project_id]
    
    def _parse_config(self, config_dict: dict[str, Any]) -> ProjectionConfig:
        """Parse configuration dictionary into ProjectionConfig."""
        style = config_dict.get("style", "thematic")
        length = config_dict.get("length", "standard")
        update_mode = config_dict.get("default_update_mode", "evolve")
        
        return ProjectionConfig(
            style=ProjectionStyle(style) if style in [s.value for s in ProjectionStyle] else ProjectionStyle.THEMATIC,
            length=ProjectionLength(length) if length in [l.value for l in ProjectionLength] else ProjectionLength.STANDARD,
            default_update_mode=UpdateMode(update_mode) if update_mode in [m.value for m in UpdateMode] else UpdateMode.EVOLVE,
            auto_update_on_content=config_dict.get("auto_update_on_content", False),
            contributor_filter=config_dict.get("contributor_filter"),
            tag_filter=config_dict.get("tag_filter"),
            suggested_sections=config_dict.get("suggested_sections"),
            voice_guidance=config_dict.get("voice_guidance"),
        )
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def add_content_item(self, item: ContentItem) -> None:
        """Add a content item (for testing/integration)."""
        self._content_items[item.id] = item
        pool = self._get_or_create_pool(item.project_id)
        pool.add_content(item.id, item.contributor_id, item.tags)
    
    def get_projection(self, projection_id: str) -> DocumentProjection | None:
        """Get a projection by ID."""
        return self._projections.get(projection_id)
    
    def get_project_projections(self, project_id: str) -> list[DocumentProjection]:
        """Get all projections for a project."""
        projection_ids = self._project_projections.get(project_id, [])
        return [
            self._projections[pid]
            for pid in projection_ids
            if pid in self._projections
        ]
    
    def get_update_options(
        self,
        projection_id: str,
    ) -> dict[str, Any] | None:
        """Get available update options for a projection."""
        projection = self._projections.get(projection_id)
        if not projection:
            return None
        
        pool = self._content_pools.get(projection.project_id)
        if not pool:
            return projection.get_update_options([])
        
        return projection.get_update_options(pool.content_ids)
    
    def lock_section(
        self,
        projection_id: str,
        section_id: str,
        user_id: str,
        reason: str = "approved",
    ) -> bool:
        """Lock a section in a projection."""
        projection = self._projections.get(projection_id)
        if projection:
            return projection.lock_section(section_id, user_id, reason)
        return False
    
    def unlock_section(self, projection_id: str, section_id: str) -> bool:
        """Unlock a section in a projection."""
        projection = self._projections.get(projection_id)
        if projection:
            return projection.unlock_section(section_id)
        return False
    
    def edit_section(
        self,
        projection_id: str,
        section_id: str,
        new_content: str,
        lock: bool = True,
        user_id: str | None = None,
    ) -> bool:
        """Edit a section's content and optionally lock it."""
        projection = self._projections.get(projection_id)
        if not projection:
            return False
        
        section = projection.get_section(section_id)
        if not section:
            return False
        
        section.finish_editing(new_content, lock=lock, user_id=user_id)
        projection._update_stats()
        return True
    
    def revert_section(
        self,
        projection_id: str,
        section_id: str,
        version: int,
    ) -> bool:
        """Revert a section to a previous version."""
        projection = self._projections.get(projection_id)
        if not projection:
            return False
        
        section = projection.get_section(section_id)
        if not section:
            return False
        
        return section.revert_to_version(version)
