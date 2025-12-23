"""
Tests for the projection system.

Core principle: content is primary, documents are projections.
"""

import pytest
from memoir.core.models import ContentItem, ContentType
from memoir.core.projections import (
    ContentPool,
    DocumentProjection,
    ProjectedSection,
    ProjectionConfig,
    ProjectionStyle,
    SectionState,
)
from memoir.services.projection import ProjectionService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def content_item():
    """A single content item."""
    return ContentItem(
        id="c1",
        project_id="proj1",
        contributor_id="contrib1",
        content_type=ContentType.TEXT,
        source_interface="web_form",
        content={"answer_text": "I grew up on a farm in Iowa."},
        tags=["childhood"],
    )


@pytest.fixture
def projection_service():
    """Fresh projection service."""
    return ProjectionService()


# =============================================================================
# ContentPool Tests
# =============================================================================


class TestContentPool:
    def test_add_content(self):
        pool = ContentPool(project_id="proj1")
        pool.add_content("c1", "contrib1", ["tag1", "tag2"])
        
        assert "c1" in pool.content_ids
        assert "contrib1" in pool.contributor_ids
        assert pool.tags == {"tag1", "tag2"}
        assert pool.total_items == 1

    def test_no_duplicates(self):
        pool = ContentPool(project_id="proj1")
        pool.add_content("c1", "contrib1", ["tag1"])
        pool.add_content("c1", "contrib1", ["tag1"])  # Same ID
        
        assert pool.total_items == 1


# =============================================================================
# ProjectedSection Tests
# =============================================================================


class TestProjectedSection:
    def test_lock_unlock(self):
        section = ProjectedSection(title="Childhood", content="Some text")
        section.state = SectionState.GENERATED
        
        # Lock it
        section.lock("user1", reason="approved")
        assert section.state == SectionState.LOCKED
        assert section.locked_by == "user1"
        assert not section.can_regenerate
        
        # Unlock it
        section.unlock()
        assert section.state == SectionState.GENERATED
        assert section.can_regenerate

    def test_regeneratable_states(self):
        section = ProjectedSection(title="Test")
        
        section.state = SectionState.EMPTY
        assert section.can_regenerate
        
        section.state = SectionState.GENERATED
        assert section.can_regenerate
        
        section.state = SectionState.LOCKED
        assert not section.can_regenerate
        
        section.state = SectionState.DRAFT
        assert not section.can_regenerate


# =============================================================================
# DocumentProjection Tests
# =============================================================================


class TestDocumentProjection:
    def test_add_sections(self):
        proj = DocumentProjection(project_id="proj1", name="My Story")
        proj.add_section(ProjectedSection(title="Chapter 1", content="Text"))
        proj.add_section(ProjectedSection(title="Chapter 2", content="More text"))
        
        assert len(proj.sections) == 2
        assert proj.sections[0].order == 0
        assert proj.sections[1].order == 1

    def test_get_locked_vs_regeneratable(self):
        proj = DocumentProjection(project_id="proj1", name="Test")
        
        s1 = ProjectedSection(title="Locked", state=SectionState.LOCKED)
        s2 = ProjectedSection(title="Generated", state=SectionState.GENERATED)
        s3 = ProjectedSection(title="Also Locked", state=SectionState.LOCKED)
        
        proj.add_section(s1)
        proj.add_section(s2)
        proj.add_section(s3)
        
        assert len(proj.get_locked_sections()) == 2
        assert len(proj.get_regeneratable_sections()) == 1

    def test_word_count(self):
        proj = DocumentProjection(project_id="proj1", name="Test")
        proj.add_section(ProjectedSection(title="A", content="one two three"))
        proj.add_section(ProjectedSection(title="B", content="four five"))
        
        assert proj.word_count == 5


# =============================================================================
# ProjectionService Tests
# =============================================================================


class TestProjectionService:
    @pytest.mark.asyncio
    async def test_generate_projection(self, projection_service, content_item):
        projection_service.add_content_item(content_item)
        
        proj = await projection_service.generate_projection(
            project_id="proj1",
            name="Test Story",
            config=ProjectionConfig(style=ProjectionStyle.THEMATIC),
        )
        
        assert proj.name == "Test Story"
        assert proj.project_id == "proj1"
        assert len(proj.sections) > 0

    @pytest.mark.asyncio
    async def test_locked_section_preserved_on_regenerate(self, projection_service, content_item):
        """The key behavior: locked sections don't change on regenerate."""
        projection_service.add_content_item(content_item)
        
        # Generate
        proj = await projection_service.generate_projection(
            project_id="proj1",
            name="Test",
            config=ProjectionConfig(),
        )
        
        # Lock first section
        first_section = proj.sections[0]
        original_content = first_section.content
        projection_service.lock_section(proj.id, first_section.id, "user1")
        
        # Add more content
        projection_service.add_content_item(ContentItem(
            id="c2",
            project_id="proj1",
            contributor_id="contrib1",
            content_type=ContentType.TEXT,
            source_interface="voice",
            content={"answer_text": "New story about school."},
            tags=["education"],
        ))
        
        # Regenerate
        await projection_service.regenerate_projection(proj)
        
        # Locked section unchanged
        assert proj.sections[0].content == original_content
        assert proj.sections[0].state == SectionState.LOCKED

    @pytest.mark.asyncio
    async def test_multiple_projections_same_content(self, projection_service, content_item):
        projection_service.add_content_item(content_item)
        
        # Two different projections
        thematic = await projection_service.generate_projection(
            project_id="proj1",
            name="Thematic View",
            config=ProjectionConfig(style=ProjectionStyle.THEMATIC),
        )
        chrono = await projection_service.generate_projection(
            project_id="proj1",
            name="Timeline View",
            config=ProjectionConfig(style=ProjectionStyle.CHRONOLOGICAL),
        )
        
        all_projs = projection_service.get_project_projections("proj1")
        assert len(all_projs) == 2
        assert thematic.id != chrono.id

    def test_edit_and_lock_section(self, projection_service):
        # Create projection manually for this test
        proj = DocumentProjection(project_id="proj1", name="Test")
        proj.add_section(ProjectedSection(
            id="sec1",
            title="Chapter",
            content="Original",
            state=SectionState.GENERATED,
        ))
        projection_service._projections[proj.id] = proj
        
        # Edit with lock
        projection_service.edit_section(
            proj.id, "sec1",
            new_content="User edited version",
            lock=True,
        )
        
        section = proj.get_section("sec1")
        assert section.content == "User edited version"
        assert section.state == SectionState.LOCKED

