"""
FastAPI application for the Memoir platform.

This is the main HTTP API that frontends and other services interact with.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from memoir.config import get_settings, Settings
from memoir.storage import create_local_storage, StorageProvider
from memoir.services.projection import ProjectionService
from memoir.core.models import ContentItem, ContentType
from memoir.core.projections import (
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    UpdateMode,
)
from memoir.interfaces import VoiceRecorderInterface, WebFormInterface
from memoir.auth import require, require_auth, AuthContext, Capability


# =============================================================================
# App State
# =============================================================================


class AppState:
    """Application state - initialized at startup."""
    
    storage: StorageProvider
    projection_service: ProjectionService
    voice_interface: VoiceRecorderInterface
    form_interface: WebFormInterface


state = AppState()


# =============================================================================
# Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup app resources."""
    settings = get_settings()
    
    # Initialize error tracking (Sentry)
    try:
        from memoir.integrations.sentry import init_sentry
        if init_sentry():
            print("✅ Sentry error tracking enabled")
    except ImportError:
        pass  # Sentry not installed
    
    # Initialize storage
    state.storage = create_local_storage()
    
    # Initialize services
    state.projection_service = ProjectionService()
    
    # Initialize input interfaces
    state.voice_interface = VoiceRecorderInterface(storage=state.storage)
    state.form_interface = WebFormInterface(storage=state.storage)
    
    print(f"🚀 Memoir API starting in {settings.environment} mode")
    
    yield
    
    print("👋 Memoir API shutting down")


# =============================================================================
# App Setup
# =============================================================================


app = FastAPI(
    title="Memoir API",
    description="API for collecting life stories and creating personalized documents",
    version="0.1.0",
    lifespan=lifespan,
)


# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from memoir.auth import auth_router
app.include_router(auth_router)


# =============================================================================
# Dependencies
# =============================================================================


def get_storage() -> StorageProvider:
    return state.storage


def get_projection_service() -> ProjectionService:
    return state.projection_service


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateProjectRequest(BaseModel):
    name: str
    product_id: str = "life_story"
    subject_name: str


class CreateProjectResponse(BaseModel):
    project_id: str
    name: str


class AddContentRequest(BaseModel):
    project_id: str
    contributor_id: str
    content_type: str = "text"
    source_interface: str = "web_form"
    content: dict[str, Any]
    tags: list[str] = []


class AddContentResponse(BaseModel):
    content_id: str


class GenerateProjectionRequest(BaseModel):
    project_id: str
    name: str = "Document"
    style: str = "thematic"
    length: str = "standard"
    suggested_sections: list[str] | None = None
    default_update_mode: str = "evolve"
    auto_update_on_content: bool = False
    # Multi-contributor options
    merge_strategy: str = "weave"  # weave, separate_voices, subject_primary, equal_voices, annotated
    show_attributions: bool = False
    subject_contributor_id: str | None = None  # ID of the main subject


class UpdateProjectionRequest(BaseModel):
    mode: str = "evolve"  # evolve, regenerate, refresh, append
    section_ids: list[str] | None = None  # Optional: specific sections to update


class ProjectionResponse(BaseModel):
    projection_id: str
    name: str
    version: int
    sections: list[dict[str, Any]]
    word_count: int


# Contributor models
class AddContributorRequest(BaseModel):
    project_id: str
    name: str
    role: str = "family"  # subject, family, friend, colleague, caregiver, interviewer
    relationship: str | None = None  # "daughter", "grandson", "best friend", etc.
    email: str | None = None


class ContributorResponse(BaseModel):
    contributor_id: str
    name: str
    role: str
    relationship: str | None
    status: str
    invite_token: str | None


class LockSectionRequest(BaseModel):
    projection_id: str
    section_id: str
    reason: str = "approved"


class EditSectionRequest(BaseModel):
    projection_id: str
    section_id: str
    content: str
    lock: bool = True


class RevertSectionRequest(BaseModel):
    projection_id: str
    section_id: str
    version: int


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "memoir-api"}


# =============================================================================
# Projects
# =============================================================================


@app.post("/projects", response_model=CreateProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    storage: StorageProvider = Depends(get_storage),
):
    """Create a new memoir project."""
    import uuid
    
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    
    await storage.metadata.save("projects", project_id, {
        "id": project_id,
        "name": request.name,
        "product_id": request.product_id,
        "subject_name": request.subject_name,
        "status": "active",
    })
    
    return CreateProjectResponse(project_id=project_id, name=request.name)


@app.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    ctx: AuthContext = Depends(require("project.read")),
    storage: StorageProvider = Depends(get_storage),
):
    """Get a project by ID."""
    project = await storage.metadata.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Include user's permissions in response
    return {
        **project,
        "_permissions": {
            "can_edit": ctx.can("project.edit"),
            "can_delete": ctx.can("project.delete"),
            "can_manage_contributors": ctx.can("project.manage_contributors"),
            "role": ctx.project_role.value if ctx.project_role else None,
        }
    }


# =============================================================================
# Content
# =============================================================================


@app.post("/content", response_model=AddContentResponse)
async def add_content(
    request: AddContentRequest,
    storage: StorageProvider = Depends(get_storage),
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Add content to a project."""
    import uuid
    
    content_id = f"content_{uuid.uuid4().hex[:12]}"
    
    # Create content item
    content_item = ContentItem(
        id=content_id,
        project_id=request.project_id,
        contributor_id=request.contributor_id,
        content_type=ContentType(request.content_type),
        source_interface=request.source_interface,
        content=request.content,
        tags=request.tags,
    )
    
    # Store in metadata
    await storage.metadata.save("content_items", content_id, content_item.model_dump())
    
    # Add to projection service's pool
    projection_service.add_content_item(content_item)
    
    return AddContentResponse(content_id=content_id)


@app.get("/projects/{project_id}/content")
async def list_content(
    project_id: str,
    ctx: AuthContext = Depends(require("content.read")),
    storage: StorageProvider = Depends(get_storage),
):
    """List all content for a project."""
    items = await storage.metadata.query("content_items", {"project_id": project_id})
    return {
        "items": items,
        "count": len(items),
        "_permissions": {
            "can_create": ctx.can("content.create"),
            "can_edit": ctx.can("content.edit"),
            "can_delete": ctx.can("content.delete"),
        }
    }


# =============================================================================
# Contributors (Multi-contributor support)
# =============================================================================


@app.post("/projects/{project_id}/contributors", response_model=ContributorResponse)
async def add_contributor(
    project_id: str,
    request: AddContributorRequest,
    storage: StorageProvider = Depends(get_storage),
):
    """
    Add a contributor to a project.
    
    Contributors can be:
    - subject: The person whose life story this is
    - family: Family members (specify relationship like "daughter", "grandson")
    - friend: Close friends
    - colleague: Work colleagues
    - caregiver: Professional caregivers
    - interviewer: Professional interviewers/biographers
    """
    from memoir.core.models import Contributor, ContributorRole, ContributorStatus
    
    contributor = Contributor(
        project_id=project_id,
        name=request.name,
        role=ContributorRole(request.role),
        relationship=request.relationship,
        email=request.email,
        status=ContributorStatus.ACTIVE,
    )
    
    # Store contributor
    await storage.metadata.save("contributors", contributor.id, contributor.model_dump())
    
    return ContributorResponse(
        contributor_id=contributor.id,
        name=contributor.name,
        role=contributor.role.value,
        relationship=contributor.relationship,
        status=contributor.status.value,
        invite_token=contributor.invite_token,
    )


@app.get("/projects/{project_id}/contributors")
async def list_contributors(
    project_id: str,
    storage: StorageProvider = Depends(get_storage),
):
    """List all contributors for a project."""
    contributors = await storage.metadata.query("contributors", {"project_id": project_id})
    return {
        "contributors": contributors,
        "count": len(contributors),
    }


@app.get("/projects/{project_id}/contributors/{contributor_id}")
async def get_contributor(
    project_id: str,
    contributor_id: str,
    storage: StorageProvider = Depends(get_storage),
):
    """Get a specific contributor."""
    contributor = await storage.metadata.get("contributors", contributor_id)
    if not contributor:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return contributor


@app.get("/projects/{project_id}/contributor-stats")
async def get_contributor_stats(
    project_id: str,
    storage: StorageProvider = Depends(get_storage),
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """
    Get contribution statistics for all contributors.
    
    Shows how much each person has contributed to the life story.
    """
    # Get all contributors
    contributors = await storage.metadata.query("contributors", {"project_id": project_id})
    
    # Get all content
    content_items = await storage.metadata.query("content_items", {"project_id": project_id})
    
    # Count content per contributor
    content_by_contributor: dict[str, int] = {}
    for item in content_items:
        contrib_id = item.get("contributor_id")
        if contrib_id:
            content_by_contributor[contrib_id] = content_by_contributor.get(contrib_id, 0) + 1
    
    # Build stats
    stats = []
    for contributor in contributors:
        contrib_id = contributor.get("id")
        stats.append({
            "contributor_id": contrib_id,
            "name": contributor.get("name"),
            "role": contributor.get("role"),
            "relationship": contributor.get("relationship"),
            "content_items": content_by_contributor.get(contrib_id, 0),
            "status": contributor.get("status"),
        })
    
    # Sort by content count (most contributions first)
    stats.sort(key=lambda x: x["content_items"], reverse=True)
    
    return {
        "project_id": project_id,
        "total_contributors": len(contributors),
        "total_content_items": len(content_items),
        "contributors": stats,
    }


# =============================================================================
# Voice Recording (Whisper transcription)
# =============================================================================


class TranscribeResponse(BaseModel):
    content_id: str
    text: str
    language: str


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    project_id: str = "",
    contributor_id: str = "",
    question: str = "",
    question_id: str = "",
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """
    Transcribe audio using Whisper and create a content item.
    
    If project_id and contributor_id are provided, the transcription
    is stored as a ContentItem and added to the content pool.
    """
    # Validate file type
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    audio_data = await audio.read()
    
    if project_id and contributor_id:
        # Full processing: store and transcribe
        content_item = await state.voice_interface.process(
            audio_data=audio_data,
            project_id=project_id,
            contributor_id=contributor_id,
            question=question or None,
            question_id=question_id or None,
            filename=audio.filename or "recording.wav",
        )
        
        # Add to projection service
        projection_service.add_content_item(content_item)
        
        return TranscribeResponse(
            content_id=content_item.id,
            text=content_item.content["answer_text"],
            language=content_item.content.get("language", "en"),
        )
    else:
        # Just transcribe, don't store
        result = await state.voice_interface.transcribe(
            audio_data=audio_data,
            filename=audio.filename or "recording.wav",
        )
        return TranscribeResponse(
            content_id="",
            text=result["text"],
            language=result.get("language", "en"),
        )


# =============================================================================
# Web Form Input
# =============================================================================


class FormAnswerRequest(BaseModel):
    project_id: str
    contributor_id: str
    question: str
    answer: str
    question_id: str | None = None


class FormBatchRequest(BaseModel):
    project_id: str
    contributor_id: str
    qa_pairs: list[dict[str, str]]


class BioDataRequest(BaseModel):
    project_id: str
    contributor_id: str
    bio_data: dict[str, Any]


@app.post("/form/answer", response_model=AddContentResponse)
async def submit_form_answer(
    request: FormAnswerRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Submit a single form answer."""
    content_item = await state.form_interface.process(
        project_id=request.project_id,
        contributor_id=request.contributor_id,
        question=request.question,
        answer=request.answer,
        question_id=request.question_id,
    )
    
    projection_service.add_content_item(content_item)
    
    return AddContentResponse(content_id=content_item.id)


@app.post("/form/batch")
async def submit_form_batch(
    request: FormBatchRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Submit multiple Q&A pairs at once."""
    content_items = await state.form_interface.process_batch(
        project_id=request.project_id,
        contributor_id=request.contributor_id,
        qa_pairs=request.qa_pairs,
    )
    
    for item in content_items:
        projection_service.add_content_item(item)
    
    return {
        "content_ids": [item.id for item in content_items],
        "count": len(content_items),
    }


@app.post("/form/bio", response_model=AddContentResponse)
async def submit_bio(
    request: BioDataRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Submit bio/profile data."""
    content_item = await state.form_interface.process_bio(
        project_id=request.project_id,
        contributor_id=request.contributor_id,
        bio_data=request.bio_data,
    )
    
    projection_service.add_content_item(content_item)
    
    return AddContentResponse(content_id=content_item.id)


# =============================================================================
# Projections
# =============================================================================


@app.post("/projections", response_model=ProjectionResponse)
async def generate_projection(
    request: GenerateProjectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Generate a document projection from content."""
    
    config = ProjectionConfig(
        style=ProjectionStyle(request.style),
        length=ProjectionLength(request.length),
        suggested_sections=request.suggested_sections,
        default_update_mode=UpdateMode(request.default_update_mode),
        auto_update_on_content=request.auto_update_on_content,
    )
    
    projection = await projection_service.generate_projection(
        project_id=request.project_id,
        name=request.name,
        config=config,
    )
    
    return ProjectionResponse(
        projection_id=projection.id,
        name=projection.name,
        version=projection.version,
        sections=[
            {
                "id": s.id,
                "title": s.title,
                "content": s.content,
                "state": s.state.value,
                "order": s.order,
                "version": s.version,
                "is_locked": s.is_locked,
            }
            for s in projection.sections
        ],
        word_count=projection.word_count,
    )


@app.get("/projections/{projection_id}")
async def get_projection(
    projection_id: str,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Get a projection by ID."""
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    return {
        "id": projection.id,
        "name": projection.name,
        "project_id": projection.project_id,
        "version": projection.version,
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "content": s.content,
                "state": s.state.value,
                "order": s.order,
                "version": s.version,
                "is_locked": s.is_locked,
                "history_count": len(s.history),
            }
            for s in projection.sections
        ],
        "word_count": projection.word_count,
        "last_updated": projection.updated_at.isoformat() if projection.updated_at else None,
        "last_regenerated": projection.last_regenerated.isoformat() if projection.last_regenerated else None,
        "context": {
            "themes": [t.theme for t in projection.context.themes],
            "emotional_tone": projection.context.emotional_tone,
            "key_facts": projection.context.key_facts,
        },
    }


@app.get("/projections/{projection_id}/update-options")
async def get_update_options(
    projection_id: str,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Get available update options for a projection."""
    options = projection_service.get_update_options(projection_id)
    if not options:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    return options


@app.post("/projections/{projection_id}/update")
async def update_projection(
    projection_id: str,
    request: UpdateProjectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """
    Update a projection with specified mode.
    
    Modes:
    - evolve: Integrate new content while preserving structure
    - regenerate: Fully regenerate unlocked sections
    - refresh: Only update sections with new relevant content
    - append: Add new content to existing sections
    """
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    mode = UpdateMode(request.mode)
    
    if request.section_ids:
        # Update specific sections
        for section_id in request.section_ids:
            section = projection.get_section(section_id)
            if section and section.can_regenerate:
                await projection_service._update_section(projection, section, mode)
        projection._update_stats()
    else:
        # Update all eligible sections
        await projection_service.update_projection(projection, mode)
    
    return {
        "status": "updated",
        "mode": mode.value,
        "version": projection.version,
        "word_count": projection.word_count,
        "sections_updated": len(projection.get_regeneratable_sections()),
    }


@app.post("/projections/{projection_id}/regenerate")
async def regenerate_projection(
    projection_id: str,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Regenerate a projection (full regeneration respecting locked sections)."""
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    await projection_service.update_projection(projection, UpdateMode.REGENERATE)
    
    return {
        "status": "regenerated",
        "version": projection.version,
        "locked_sections": len(projection.get_locked_sections()),
        "regenerated_sections": len(projection.get_regeneratable_sections()),
    }


@app.post("/projections/lock-section")
async def lock_section(
    request: LockSectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Lock a section to prevent updates."""
    success = projection_service.lock_section(
        projection_id=request.projection_id,
        section_id=request.section_id,
        user_id="current_user",  # TODO: Get from auth
        reason=request.reason,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {"status": "locked"}


@app.post("/projections/unlock-section")
async def unlock_section(
    request: LockSectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Unlock a section to allow updates."""
    success = projection_service.unlock_section(
        projection_id=request.projection_id,
        section_id=request.section_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {"status": "unlocked"}


@app.post("/projections/edit-section")
async def edit_section(
    request: EditSectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Edit a section's content."""
    success = projection_service.edit_section(
        projection_id=request.projection_id,
        section_id=request.section_id,
        new_content=request.content,
        lock=request.lock,
        user_id="current_user",  # TODO: Get from auth
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {"status": "edited", "locked": request.lock}


@app.post("/projections/revert-section")
async def revert_section(
    request: RevertSectionRequest,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Revert a section to a previous version."""
    success = projection_service.revert_section(
        projection_id=request.projection_id,
        section_id=request.section_id,
        version=request.version,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Section or version not found")
    
    return {"status": "reverted", "version": request.version}


@app.get("/projections/{projection_id}/section/{section_id}/history")
async def get_section_history(
    projection_id: str,
    section_id: str,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Get version history for a section."""
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    section = projection.get_section(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {
        "section_id": section_id,
        "current_version": section.version,
        "history": [
            {
                "version": h.version,
                "trigger": h.trigger,
                "created_at": h.created_at.isoformat(),
                "created_by": h.created_by,
                "content_preview": h.content[:200] + "..." if len(h.content) > 200 else h.content,
            }
            for h in section.history
        ],
    }


@app.get("/projects/{project_id}/projections")
async def list_projections(
    project_id: str,
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """List all projections for a project."""
    projections = projection_service.get_project_projections(project_id)
    
    return {
        "projections": [
            {
                "id": p.id,
                "name": p.name,
                "version": p.version,
                "sections_count": len(p.sections),
                "locked_count": len(p.get_locked_sections()),
                "word_count": p.word_count,
                "last_updated": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projections
        ]
    }


# =============================================================================
# Export
# =============================================================================


@app.get("/projections/{projection_id}/export")
async def export_projection(
    projection_id: str,
    format: str = "markdown",
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """Export a projection to various formats."""
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    if format == "markdown":
        return {
            "format": "markdown",
            "content": projection.get_full_text(),
            "version": projection.version,
        }
    elif format == "json":
        return {
            "format": "json",
            "content": {
                "title": projection.name,
                "version": projection.version,
                "sections": [
                    {"title": s.title, "content": s.content}
                    for s in projection.sections
                ],
            },
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")


# =============================================================================
# Translation
# =============================================================================


class TranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: str = "en"
    context: str = ""


class TranslateProjectionRequest(BaseModel):
    target_language: str
    source_language: str = "en"


@app.post("/translate")
async def translate_text(request: TranslateRequest):
    """
    Translate text to target language.
    
    Uses LLM for high-quality translation with caching.
    """
    from memoir.i18n import translate, SUPPORTED_LANGUAGES, get_language_name
    
    # Validate language
    valid_codes = [lang.value for lang in SUPPORTED_LANGUAGES]
    if request.target_language not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {request.target_language}. Supported: {valid_codes}"
        )
    
    translated = await translate(
        request.text,
        target=request.target_language,
        source=request.source_language,
        context=request.context,
    )
    
    return {
        "original": request.text,
        "translated": translated,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "target_language_name": get_language_name(request.target_language),
    }


@app.get("/projections/{projection_id}/translate/{target_language}")
async def translate_projection_endpoint(
    projection_id: str,
    target_language: str,
    source_language: str = "en",
    projection_service: ProjectionService = Depends(get_projection_service),
):
    """
    Get a projection translated to target language.
    
    Translates:
    - Document name and description
    - All section titles and content
    - Theme names and descriptions
    
    Results are cached for efficiency.
    """
    from memoir.i18n import translate_projection, SUPPORTED_LANGUAGES
    
    # Validate language
    valid_codes = [lang.value for lang in SUPPORTED_LANGUAGES]
    if target_language not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {target_language}"
        )
    
    projection = projection_service.get_projection(projection_id)
    if not projection:
        raise HTTPException(status_code=404, detail="Projection not found")
    
    # Convert to dict and translate
    projection_dict = {
        "id": projection.id,
        "name": projection.name,
        "description": projection.description,
        "version": projection.version,
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "content": s.content,
                "summary": s.summary,
                "state": s.state.value,
                "is_locked": s.state.value == "locked",
            }
            for s in projection.sections
        ],
        "context": {
            "themes": [
                {"theme": t.theme, "description": t.description}
                for t in projection.context.themes
            ]
        },
        "word_count": projection.word_count,
    }
    
    translated = await translate_projection(
        projection_dict,
        target=target_language,
        source=source_language,
    )
    
    return translated


@app.get("/languages")
async def list_languages():
    """List all supported languages for translation."""
    from memoir.i18n import SUPPORTED_LANGUAGES, get_language_name
    
    return {
        "languages": [
            {
                "code": lang.value,
                "name": get_language_name(lang.value),
            }
            for lang in SUPPORTED_LANGUAGES
        ]
    }
